"""Service layer for NAS-hosted raw Copart proxy and connector endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import logging
from threading import Lock
from time import perf_counter
from typing import Callable, Optional

from cryptography.fernet import Fernet, InvalidToken
import httpx

from cartrap.config import Settings, get_settings
from cartrap.core.logging import make_log_extra, new_correlation_id
from cartrap.modules.copart_provider.client import (
    CopartConnectorBootstrapResult,
    CopartConnectorExecutionResult,
    CopartEncryptedSessionBundle,
    CopartHttpClient,
    CopartHttpPayloadResponse,
    CopartSessionBundle,
)
from cartrap.modules.copart_provider.errors import (
    CopartAuthenticationError,
    CopartChallengeError,
    CopartConfigurationError,
    CopartRateLimitError,
    CopartSessionInvalidError,
)


_BOOTSTRAP_ATTEMPTS: dict[str, list[datetime]] = {}
_BOOTSTRAP_ATTEMPTS_LOCK = Lock()


@dataclass
class GatewayProxyResponse:
    payload: Optional[dict]
    etag: Optional[str]
    not_modified: bool = False


@dataclass
class GatewayConnectorResponse:
    session_bundle: CopartEncryptedSessionBundle
    status: str
    verified_at: Optional[datetime]
    account_label: Optional[str] = None
    payload: Optional[dict] = None
    etag: Optional[str] = None
    not_modified: bool = False
    used_at: Optional[datetime] = None


logger = logging.getLogger(__name__)


class CopartGatewayService:
    def __init__(
        self,
        settings: Optional[Settings] = None,
        client_factory: Optional[Callable[[], CopartHttpClient]] = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._client_factory = client_factory or self._build_default_client

    def proxy_search(self, payload: dict, etag: Optional[str] = None) -> GatewayProxyResponse:
        return self._execute_proxy_call(
            operation="copart_gateway.proxy.search",
            callback=lambda client, correlation_id: client.search_with_metadata(
                payload,
                etag=etag,
                correlation_id=correlation_id,
            ),
        )

    def proxy_search_count(self, payload: dict, etag: Optional[str] = None) -> GatewayProxyResponse:
        return self._execute_proxy_call(
            operation="copart_gateway.proxy.search_count",
            callback=lambda client, correlation_id: client.search_count_with_metadata(
                payload,
                etag=etag,
                correlation_id=correlation_id,
            ),
        )

    def proxy_lot_details(self, lot_number: int, etag: Optional[str] = None) -> GatewayProxyResponse:
        return self._execute_proxy_call(
            operation="copart_gateway.proxy.lot_details",
            callback=lambda client, correlation_id: client.lot_details_with_metadata(
                str(lot_number),
                etag=etag,
                correlation_id=correlation_id,
            ),
            lot_number=lot_number,
        )

    def proxy_search_keywords(self) -> GatewayProxyResponse:
        return self._execute_proxy_call(
            operation="copart_gateway.proxy.search_keywords",
            callback=lambda client, correlation_id: client.search_keywords(correlation_id=correlation_id),
        )

    def run_connector_feasibility(self, *, username: str, password: str, lot_number: int) -> GatewayConnectorResponse:
        bootstrap = self.bootstrap_connector(username=username, password=password)
        return self.execute_connector_lot_details(bootstrap.session_bundle, lot_number=lot_number)

    def bootstrap_connector(self, *, username: str, password: str) -> GatewayConnectorResponse:
        self._enforce_connect_rate_limit(username)
        client = self._client_factory()
        try:
            result = client.bootstrap_connector_session(username=username, password=password)
        finally:
            client.close()
        raw_bundle = self._require_raw_bundle(result.bundle)
        return GatewayConnectorResponse(
            session_bundle=self._encrypt_session_bundle(raw_bundle),
            status=result.connection_status,
            verified_at=result.verified_at,
            account_label=result.account_label,
        )

    def verify_connector(self, session_bundle: CopartEncryptedSessionBundle) -> GatewayConnectorResponse:
        client = self._client_factory()
        try:
            raw_bundle = self._decrypt_session_bundle(session_bundle)
            result = client.verify_connector_session(raw_bundle)
        finally:
            client.close()
        return self._to_connector_response(result)

    def execute_connector_search(
        self,
        session_bundle: CopartEncryptedSessionBundle,
        *,
        search_payload: dict,
    ) -> GatewayConnectorResponse:
        client = self._client_factory()
        try:
            raw_bundle = self._decrypt_session_bundle(session_bundle)
            result = client.search_with_connector_session(search_payload, raw_bundle)
        finally:
            client.close()
        return self._to_connector_response(result)

    def execute_connector_lot_details(
        self,
        session_bundle: CopartEncryptedSessionBundle,
        *,
        lot_number: int,
        etag: Optional[str] = None,
    ) -> GatewayConnectorResponse:
        client = self._client_factory()
        try:
            raw_bundle = self._decrypt_session_bundle(session_bundle)
            result = client.lot_details_with_connector_session(str(lot_number), raw_bundle, etag=etag)
        finally:
            client.close()
        return self._to_connector_response(result)

    def _build_default_client(self) -> CopartHttpClient:
        return CopartHttpClient(
            settings=self._settings.model_copy(
                update={
                    "copart_gateway_base_url": None,
                }
            )
        )

    @staticmethod
    def _to_gateway_response(response: CopartHttpPayloadResponse) -> GatewayProxyResponse:
        return GatewayProxyResponse(payload=response.payload, etag=response.etag, not_modified=response.not_modified)

    def _to_connector_response(self, response: CopartConnectorExecutionResult) -> GatewayConnectorResponse:
        encrypted_bundle = None
        if response.bundle is not None:
            encrypted_bundle = self._encrypt_session_bundle(self._require_raw_bundle(response.bundle))
        return GatewayConnectorResponse(
            session_bundle=encrypted_bundle or CopartEncryptedSessionBundle(
                encrypted_bundle="",
                key_version=self._settings.copart_connector_encryption_key_version,
                captured_at=None,
                expires_at=None,
            ),
            payload=response.payload,
            etag=response.etag,
            not_modified=response.not_modified,
            status=response.connection_status,
            verified_at=response.verified_at,
            used_at=response.used_at,
        )

    def _execute_proxy_call(self, *, operation: str, callback, **metadata) -> GatewayProxyResponse:
        correlation_id = new_correlation_id("gateway-proxy")
        started_at = perf_counter()
        logger.info(
            f"{operation}.start",
            extra=make_log_extra(
                f"{operation}.start",
                correlation_id=correlation_id,
                **metadata,
            ),
        )
        client = self._client_factory()
        try:
            response = callback(client, correlation_id)
        except httpx.HTTPStatusError:
            logger.exception(
                f"{operation}.failed",
                extra=make_log_extra(
                    f"{operation}.failed",
                    correlation_id=correlation_id,
                    duration_ms=round((perf_counter() - started_at) * 1000, 2),
                    failure_class="http_status_error",
                    **metadata,
                ),
            )
            raise
        except CopartConfigurationError:
            logger.exception(
                f"{operation}.failed",
                extra=make_log_extra(
                    f"{operation}.failed",
                    correlation_id=correlation_id,
                    duration_ms=round((perf_counter() - started_at) * 1000, 2),
                    failure_class="configuration_error",
                    **metadata,
                ),
            )
            raise
        finally:
            client.close()
        if isinstance(response, GatewayProxyResponse):
            gateway_response = response
        elif isinstance(response, CopartHttpPayloadResponse):
            gateway_response = self._to_gateway_response(response)
        else:
            gateway_response = GatewayProxyResponse(payload=response, etag=None, not_modified=False)
        logger.info(
            f"{operation}.success",
            extra=make_log_extra(
                f"{operation}.success",
                correlation_id=correlation_id,
                duration_ms=round((perf_counter() - started_at) * 1000, 2),
                not_modified=gateway_response.not_modified,
                has_etag=bool(gateway_response.etag),
                **metadata,
            ),
        )
        return gateway_response

    def _encrypt_session_bundle(self, bundle: CopartSessionBundle) -> CopartEncryptedSessionBundle:
        cipher = self._build_fernet()
        captured_at = bundle.captured_at or datetime.now(timezone.utc)
        payload = bundle.to_payload()
        encrypted = cipher.encrypt(json.dumps(payload).encode("utf-8")).decode("utf-8")
        return CopartEncryptedSessionBundle(
            encrypted_bundle=encrypted,
            key_version=self._settings.copart_connector_encryption_key_version,
            captured_at=captured_at,
            expires_at=bundle.expires_at,
        )

    def _decrypt_session_bundle(self, bundle: CopartEncryptedSessionBundle) -> CopartSessionBundle:
        cipher = self._build_fernet()
        try:
            raw_payload = cipher.decrypt(bundle.encrypted_bundle.encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:
            raise CopartConfigurationError("Connector session bundle could not be decrypted.") from exc
        payload = json.loads(raw_payload)
        if not isinstance(payload, dict):
            raise CopartConfigurationError("Connector session bundle payload is malformed.")
        return CopartSessionBundle.from_payload(payload)

    def _build_fernet(self) -> Fernet:
        if not self._settings.copart_connector_encryption_key:
            raise CopartConfigurationError("COPART_CONNECTOR_ENCRYPTION_KEY is required for connector operations.")
        try:
            return Fernet(self._settings.copart_connector_encryption_key.encode("utf-8"))
        except (TypeError, ValueError) as exc:
            raise CopartConfigurationError("COPART_CONNECTOR_ENCRYPTION_KEY is invalid.") from exc

    def _enforce_connect_rate_limit(self, username: str) -> None:
        window = timedelta(seconds=self._settings.copart_connector_connect_rate_limit_window_seconds)
        now = datetime.now(timezone.utc)
        with _BOOTSTRAP_ATTEMPTS_LOCK:
            attempts = [
                attempted_at
                for attempted_at in _BOOTSTRAP_ATTEMPTS.get(username.lower(), [])
                if now - attempted_at <= window
            ]
            if len(attempts) >= self._settings.copart_connector_connect_rate_limit_attempts:
                raise CopartRateLimitError("Copart connector bootstrap is rate limited.")
            attempts.append(now)
            _BOOTSTRAP_ATTEMPTS[username.lower()] = attempts

    @staticmethod
    def _require_raw_bundle(bundle: object) -> CopartSessionBundle:
        if not isinstance(bundle, CopartSessionBundle):
            raise CopartConfigurationError("Gateway direct execution expected a raw session bundle.")
        return bundle
