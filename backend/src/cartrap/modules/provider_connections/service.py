"""Business logic for per-user provider connections."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from time import perf_counter
from typing import Callable, Optional

from fastapi import HTTPException, status
from pymongo.database import Database

from cartrap.config import Settings, get_settings
from cartrap.core.logging import make_log_extra, new_correlation_id
from cartrap.modules.auction_domain.models import PROVIDER_COPART, PROVIDER_IAAI
from cartrap.modules.copart_provider.client import (
    CopartConnectorExecutionResult,
    CopartEncryptedSessionBundle,
    CopartHttpClient,
    CopartHttpPayloadResponse,
)
from cartrap.modules.copart_provider.errors import (
    CopartAuthenticationError,
    CopartChallengeError,
    CopartConfigurationError,
    CopartGatewayUnavailableError,
    CopartGatewayUpstreamError,
    CopartLoginRejectedError,
    CopartRateLimitError,
    CopartSessionInvalidError,
)
from cartrap.modules.copart_provider.service import CopartProvider
from cartrap.modules.iaai_provider.client import (
    IaaiConnectorExecutionResult,
    IaaiEncryptedSessionBundle,
    IaaiHttpClient,
    IaaiHttpPayloadResponse,
)
from cartrap.modules.iaai_provider.errors import (
    IaaiAuthenticationError,
    IaaiConfigurationError,
    IaaiRefreshError,
    IaaiSessionInvalidError,
    IaaiWafError,
)
from cartrap.modules.iaai_provider.service import IaaiProvider
from cartrap.modules.provider_connections.models import (
    PROVIDER_DISPLAY_NAMES,
    STATUS_CONNECTED,
    STATUS_DISCONNECTED,
    STATUS_ERROR,
    STATUS_EXPIRING,
    STATUS_RECONNECT_REQUIRED,
    USABLE_CONNECTION_STATUSES,
)
from cartrap.modules.provider_connections.repository import ProviderConnectionRepository
from cartrap.modules.provider_connections.schemas import ProviderConnectionDiagnosticResponse


logger = logging.getLogger(__name__)


class ProviderConnectionService:
    def __init__(
        self,
        database: Database,
        settings: Optional[Settings] = None,
        connector_client_factory: Optional[Callable[[], CopartHttpClient]] = None,
        connector_client_factories: Optional[dict[str, Callable[[], object]]] = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._repository = ProviderConnectionRepository(database)
        self._repository.ensure_indexes()
        self._connector_client_factories: dict[str, Callable[[], object]] = {
            PROVIDER_COPART: connector_client_factory or (lambda: CopartHttpClient(settings=self._settings)),
            PROVIDER_IAAI: lambda: IaaiHttpClient(settings=self._settings),
        }
        if connector_client_factories:
            self._connector_client_factories.update(connector_client_factories)

    def list_connections(self, owner_user: dict) -> dict:
        items = [self.serialize_connection(item) for item in self._repository.list_for_owner(owner_user["id"])]
        return {"items": items}

    def connect_copart(self, owner_user: dict, *, username: str, password: str, client_ip: Optional[str] = None) -> dict:
        return self.connect_provider(owner_user, provider=PROVIDER_COPART, username=username, password=password, client_ip=client_ip)

    def reconnect_copart(self, owner_user: dict, *, username: str, password: str, client_ip: Optional[str] = None) -> dict:
        return self.reconnect_provider(
            owner_user,
            provider=PROVIDER_COPART,
            username=username,
            password=password,
            client_ip=client_ip,
        )

    def disconnect_copart(self, owner_user: dict) -> dict:
        return self.disconnect_provider(owner_user, provider=PROVIDER_COPART)

    def connect_iaai(self, owner_user: dict, *, username: str, password: str, client_ip: Optional[str] = None) -> dict:
        return self.connect_provider(owner_user, provider=PROVIDER_IAAI, username=username, password=password, client_ip=client_ip)

    def reconnect_iaai(self, owner_user: dict, *, username: str, password: str, client_ip: Optional[str] = None) -> dict:
        return self.reconnect_provider(
            owner_user,
            provider=PROVIDER_IAAI,
            username=username,
            password=password,
            client_ip=client_ip,
        )

    def disconnect_iaai(self, owner_user: dict) -> dict:
        return self.disconnect_provider(owner_user, provider=PROVIDER_IAAI)

    def connect_provider(
        self,
        owner_user: dict,
        *,
        provider: str,
        username: str,
        password: str,
        client_ip: Optional[str] = None,
    ) -> dict:
        return {
            "connection": self._connect(
                owner_user,
                provider=provider,
                username=username,
                password=password,
                reconnect=False,
                client_ip=client_ip,
            )
        }

    def reconnect_provider(
        self,
        owner_user: dict,
        *,
        provider: str,
        username: str,
        password: str,
        client_ip: Optional[str] = None,
    ) -> dict:
        existing = self._repository.find_by_user_and_provider(owner_user["id"], provider)
        if existing is None or existing.get("status") == STATUS_DISCONNECTED:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{self._provider_label(provider)} connection not found.")
        return {
            "connection": self._connect(
                owner_user,
                provider=provider,
                username=username,
                password=password,
                reconnect=True,
                client_ip=client_ip,
            )
        }

    def disconnect_provider(self, owner_user: dict, *, provider: str) -> dict:
        existing = self._repository.find_by_user_and_provider(owner_user["id"], provider)
        if existing is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{self._provider_label(provider)} connection not found.")
        now = self._now()
        updated = self._repository.disconnect_connection(
            str(existing["_id"]),
            disconnected_at=now,
            updated_at=now,
        )
        if updated is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{self._provider_label(provider)} connection not found.")
        logger.info(
            "provider_connection.disconnect.success",
            extra=make_log_extra(
                "provider_connection.disconnect.success",
                owner_user_id=owner_user["id"],
                provider=provider,
                connection_id=str(updated["_id"]),
            ),
        )
        return {"connection": self.serialize_connection(updated)}

    def get_connection_diagnostic(self, owner_user_id: str, provider: str = PROVIDER_COPART) -> dict:
        provider_label = self._provider_label(provider)
        connection = self._repository.find_by_user_and_provider(owner_user_id, provider)
        if connection is None or connection.get("status") == STATUS_DISCONNECTED:
            return ProviderConnectionDiagnosticResponse(
                provider=provider,
                status="connection_missing",
                message=f"Connect {provider_label} to resume live refresh.",
            ).model_dump(mode="json")
        if connection.get("status") == STATUS_RECONNECT_REQUIRED:
            return ProviderConnectionDiagnosticResponse(
                provider=provider,
                status="reconnect_required",
                message=f"Reconnect {provider_label} to resume live refresh.",
                connection_id=str(connection["_id"]),
                reconnect_required=True,
            ).model_dump(mode="json")
        return ProviderConnectionDiagnosticResponse(
            provider=provider,
            status="ready",
            message=f"{provider_label} live connection is available.",
            connection_id=str(connection["_id"]),
            reconnect_required=False,
        ).model_dump(mode="json")

    def require_usable_connection(self, owner_user_id: str, provider: str = PROVIDER_COPART) -> dict:
        provider_label = self._provider_label(provider)
        connection = self._repository.find_by_user_and_provider(owner_user_id, provider)
        if connection is None or connection.get("status") == STATUS_DISCONNECTED:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"{provider_label} connection required.")
        if connection.get("status") == STATUS_RECONNECT_REQUIRED:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"{provider_label} connection requires re-login.")
        if connection.get("status") not in USABLE_CONNECTION_STATUSES:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"{provider_label} connection is not ready.")
        if not connection.get("encrypted_session_bundle"):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"{provider_label} connection bundle is unavailable.")
        return connection

    def build_provider_for_owner(self, owner_user_id: str, provider: str = PROVIDER_COPART):
        connection = self.require_usable_connection(owner_user_id, provider=provider)
        if provider == PROVIDER_COPART:
            return CopartProvider(client=_ProviderConnectionCopartClient(self, connection))
        if provider == PROVIDER_IAAI:
            return IaaiProvider(client=_ProviderConnectionIaaiClient(self, connection))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unsupported provider: {provider}")

    def execute_live_search(self, connection: dict, payload: dict):
        if connection["provider"] == PROVIDER_COPART:
            return self._execute_live_operation(
                connection,
                callback=lambda client, bundle: client.search_with_connector_session(payload, bundle),
            )
        if connection["provider"] == PROVIDER_IAAI:
            return self._execute_live_operation(
                connection,
                callback=lambda client, bundle: client.search_with_connector_session(payload, bundle),
            )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unsupported provider: {connection['provider']}")

    def execute_live_lot_details(self, connection: dict, reference: str, etag: str | None = None):
        return self._execute_live_operation(
            connection,
            callback=lambda client, bundle: client.lot_details_with_connector_session(reference, bundle, etag=etag),
        )

    def record_reconnect_required(self, connection: dict, *, reason_code: str, message: str) -> dict:
        if connection.get("status") == STATUS_RECONNECT_REQUIRED:
            return connection
        now = self._now()
        updated = self._repository.update_connection(
            str(connection["_id"]),
            {
                "status": STATUS_RECONNECT_REQUIRED,
                "updated_at": now,
                "last_error": {
                    "code": reason_code,
                    "message": message,
                    "retryable": False,
                    "occurred_at": now,
                },
            },
        )
        return updated or connection

    def persist_rotated_bundle(self, connection: dict, result) -> dict:
        bundle = result.bundle
        if bundle is None:
            return connection
        updated = self._repository.compare_and_swap_bundle(
            str(connection["_id"]),
            expected_bundle_version=int(connection.get("bundle_version") or 1),
            encrypted_session_bundle=bundle.encrypted_bundle,
            encrypted_session_bundle_key_version=bundle.key_version,
            bundle_captured_at=bundle.captured_at,
            bundle_expires_at=bundle.expires_at,
            updated_at=self._now(),
            status=result.connection_status,
            last_verified_at=result.verified_at,
            last_used_at=result.used_at,
        )
        if updated is not None:
            return updated
        logger.info(
            "provider_connection.bundle.cas_conflict",
            extra=make_log_extra(
                "provider_connection.bundle.cas_conflict",
                provider=connection.get("provider"),
                connection_id=str(connection["_id"]),
                owner_user_id=connection.get("owner_user_id"),
                expected_bundle_version=int(connection.get("bundle_version") or 1),
            ),
        )
        current = self._repository.find_by_user_and_provider(connection["owner_user_id"], connection["provider"])
        return current or connection

    def serialize_connection(self, document: dict) -> dict:
        status_value = document.get("status") or STATUS_ERROR
        provider = document["provider"]
        return {
            "id": str(document["_id"]),
            "provider": provider,
            "provider_label": self._provider_label(provider),
            "status": status_value,
            "account_label": document.get("account_label"),
            "connected_at": document.get("connected_at"),
            "disconnected_at": document.get("disconnected_at"),
            "last_verified_at": document.get("last_verified_at"),
            "last_used_at": document.get("last_used_at"),
            "expires_at": document.get("bundle_expires_at"),
            "reconnect_required": status_value == STATUS_RECONNECT_REQUIRED,
            "usable": status_value in USABLE_CONNECTION_STATUSES,
            "bundle_version": int(document.get("bundle_version") or 1),
            "bundle": (
                {
                    "key_version": document["encrypted_session_bundle_key_version"],
                    "captured_at": document.get("bundle_captured_at"),
                    "expires_at": document.get("bundle_expires_at"),
                }
                if document.get("encrypted_session_bundle")
                else None
            ),
            "last_error": document.get("last_error"),
            "created_at": document["created_at"],
            "updated_at": document["updated_at"],
        }

    def _connect(
        self,
        owner_user: dict,
        *,
        provider: str,
        username: str,
        password: str,
        reconnect: bool,
        client_ip: Optional[str],
    ) -> dict:
        correlation_id = new_correlation_id("provider-connect")
        started_at = perf_counter()
        client = self._connector_client_factories[provider]()
        try:
            try:
                result = client.bootstrap_connector_session(username=username, password=password, client_ip=client_ip)
            except TypeError as exc:
                if "client_ip" not in str(exc):
                    raise
                result = client.bootstrap_connector_session(username=username, password=password)
        except Exception as exc:
            self._log_connect_failure(provider, owner_user["id"], correlation_id, started_at, exc)
            self._raise_connect_exception(provider, exc)
        finally:
            client.close()

        now = self._now()
        document = self._repository.upsert_connection(
            owner_user["id"],
            provider,
            {
                "status": result.connection_status,
                "account_label": result.account_label,
                "connected_at": now,
                "disconnected_at": None,
                "last_verified_at": result.verified_at,
                "last_used_at": result.verified_at,
                "encrypted_session_bundle": result.bundle.encrypted_bundle,
                "encrypted_session_bundle_key_version": result.bundle.key_version,
                "bundle_captured_at": result.bundle.captured_at,
                "bundle_expires_at": result.bundle.expires_at,
                "bundle_version": 1,
                "last_error": None,
                "updated_at": now,
            },
        )
        logger.info(
            "provider_connection.connect.success",
            extra=make_log_extra(
                "provider_connection.connect.success",
                correlation_id=correlation_id,
                owner_user_id=owner_user["id"],
                provider=provider,
                connection_id=str(document["_id"]),
                reconnect=reconnect,
                duration_ms=round((perf_counter() - started_at) * 1000, 2),
                status=result.connection_status,
            ),
        )
        return self.serialize_connection(document)

    def _execute_live_operation(self, connection: dict, *, callback):
        provider = connection["provider"]
        if provider == PROVIDER_COPART:
            bundle = CopartEncryptedSessionBundle(
                encrypted_bundle=connection["encrypted_session_bundle"],
                key_version=connection["encrypted_session_bundle_key_version"],
                captured_at=connection.get("bundle_captured_at"),
                expires_at=connection.get("bundle_expires_at"),
            )
        elif provider == PROVIDER_IAAI:
            bundle = IaaiEncryptedSessionBundle(
                encrypted_bundle=connection["encrypted_session_bundle"],
                key_version=connection["encrypted_session_bundle_key_version"],
                captured_at=connection.get("bundle_captured_at"),
                expires_at=connection.get("bundle_expires_at"),
            )
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unsupported provider: {provider}")

        client = self._connector_client_factories[provider]()
        try:
            result = callback(client, bundle)
        except (CopartSessionInvalidError, IaaiSessionInvalidError, IaaiRefreshError) as exc:
            self.record_reconnect_required(
                connection,
                reason_code="auth_invalid",
                message=f"{self._provider_label(provider)} session expired or was rejected upstream.",
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"{self._provider_label(provider)} connection requires re-login.",
            ) from exc
        except (CopartGatewayUnavailableError, IaaiConfigurationError) as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"{self._provider_label(provider)} gateway is unavailable.",
            ) from exc
        finally:
            client.close()
        self.persist_rotated_bundle(connection, result)
        return result

    def _raise_connect_exception(self, provider: str, exc: Exception) -> None:
        provider_label = self._provider_label(provider)
        if isinstance(exc, (CopartAuthenticationError, IaaiAuthenticationError)):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"{provider_label} credentials were rejected.") from exc
        if isinstance(exc, CopartRateLimitError):
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=f"{provider_label} connect rate limit reached.") from exc
        if isinstance(exc, CopartChallengeError):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"{provider_label} connector bootstrap failed during upstream challenge replay.",
            ) from exc
        if isinstance(exc, (CopartLoginRejectedError, CopartGatewayUpstreamError, IaaiWafError)):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"{provider_label} rejected connector bootstrap request.",
            ) from exc
        if isinstance(exc, (CopartGatewayUnavailableError, CopartConfigurationError, IaaiConfigurationError)):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"{provider_label} gateway is unavailable.",
            ) from exc
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"{provider_label} connector bootstrap failed.") from exc

    def _log_connect_failure(self, provider: str, owner_user_id: str, correlation_id: str, started_at: float, exc: Exception) -> None:
        logger.warning(
            "provider_connection.connect.failed",
            extra=make_log_extra(
                "provider_connection.connect.failed",
                correlation_id=correlation_id,
                owner_user_id=owner_user_id,
                provider=provider,
                duration_ms=round((perf_counter() - started_at) * 1000, 2),
                error_type=type(exc).__name__,
            ),
        )

    @staticmethod
    def _provider_label(provider: str) -> str:
        return PROVIDER_DISPLAY_NAMES.get(provider, str(provider).upper())

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)


class _ProviderConnectionCopartClient:
    def __init__(self, service: ProviderConnectionService, connection: dict) -> None:
        self._service = service
        self._connection = connection

    def search(self, payload: dict) -> dict:
        result = self._service.execute_live_search(self._connection, payload)
        if result.payload is None:
            raise RuntimeError("Search payload is not available.")
        return result.payload

    def search_with_metadata(
        self,
        payload: dict,
        etag: str | None = None,
        correlation_id: str | None = None,
    ) -> CopartHttpPayloadResponse:
        del etag
        del correlation_id
        result = self._service.execute_live_search(self._connection, payload)
        return CopartHttpPayloadResponse(payload=result.payload, etag=result.etag, not_modified=result.not_modified)

    def search_count_with_metadata(
        self,
        payload: dict,
        etag: str | None = None,
        correlation_id: str | None = None,
    ) -> CopartHttpPayloadResponse:
        return self.search_with_metadata(payload, etag=etag, correlation_id=correlation_id)

    def lot_details_with_metadata(
        self,
        lot_number: str,
        etag: str | None = None,
        correlation_id: str | None = None,
    ) -> CopartHttpPayloadResponse:
        del correlation_id
        result = self._service.execute_live_lot_details(self._connection, lot_number, etag=etag)
        return CopartHttpPayloadResponse(payload=result.payload, etag=result.etag, not_modified=result.not_modified)

    def close(self) -> None:
        return None


class _ProviderConnectionIaaiClient:
    def __init__(self, service: ProviderConnectionService, connection: dict) -> None:
        self._service = service
        self._connection = connection

    def search(self, payload: dict) -> dict:
        result = self._service.execute_live_search(self._connection, payload)
        if result.payload is None:
            raise RuntimeError("Search payload is not available.")
        return result.payload

    def search_with_metadata(
        self,
        payload: dict,
        etag: str | None = None,
        correlation_id: str | None = None,
    ) -> IaaiHttpPayloadResponse:
        del etag
        del correlation_id
        result = self._service.execute_live_search(self._connection, payload)
        return IaaiHttpPayloadResponse(payload=result.payload, etag=result.etag, not_modified=result.not_modified)

    def search_count_with_metadata(
        self,
        payload: dict,
        etag: str | None = None,
        correlation_id: str | None = None,
    ) -> IaaiHttpPayloadResponse:
        return self.search_with_metadata(payload, etag=etag, correlation_id=correlation_id)

    def lot_details_with_metadata(
        self,
        provider_lot_id: str,
        etag: str | None = None,
        correlation_id: str | None = None,
    ) -> IaaiHttpPayloadResponse:
        del correlation_id
        result = self._service.execute_live_lot_details(self._connection, provider_lot_id, etag=etag)
        return IaaiHttpPayloadResponse(payload=result.payload, etag=result.etag, not_modified=result.not_modified)

    def close(self) -> None:
        return None
