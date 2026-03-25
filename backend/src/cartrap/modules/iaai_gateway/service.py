"""Service layer for NAS-hosted raw IAAI proxy and connector endpoints."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
from typing import Callable, Optional

from cryptography.fernet import Fernet, InvalidToken

from cartrap.config import Settings, get_settings
from cartrap.core.logging import make_log_extra, new_correlation_id
from cartrap.modules.iaai_provider.client import (
    IaaiConnectorBootstrapResult,
    IaaiConnectorExecutionResult,
    IaaiEncryptedSessionBundle,
    IaaiHttpClient,
    IaaiHttpPayloadResponse,
    IaaiSessionBundle,
)
from cartrap.modules.iaai_provider.errors import IaaiConfigurationError, IaaiError


@dataclass
class GatewayProxyResponse:
    payload: Optional[dict]
    etag: Optional[str]
    not_modified: bool = False


@dataclass
class GatewayConnectorResponse:
    session_bundle: IaaiEncryptedSessionBundle
    status: str
    verified_at: Optional[datetime]
    account_label: Optional[str] = None
    payload: Optional[dict] = None
    etag: Optional[str] = None
    not_modified: bool = False
    used_at: Optional[datetime] = None


logger = logging.getLogger(__name__)


class IaaiGatewayService:
    def __init__(
        self,
        settings: Optional[Settings] = None,
        client_factory: Optional[Callable[[], IaaiHttpClient]] = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._client_factory = client_factory or self._build_default_client

    def proxy_search(self, payload: dict, etag: Optional[str] = None) -> GatewayProxyResponse:
        client = self._client_factory()
        try:
            response = client.search_with_metadata(payload, etag=etag)
        finally:
            client.close()
        return self._to_gateway_response(response)

    def proxy_lot_details(self, provider_lot_id: str, etag: Optional[str] = None) -> GatewayProxyResponse:
        client = self._client_factory()
        try:
            response = client.lot_details_with_metadata(provider_lot_id, etag=etag)
        finally:
            client.close()
        return self._to_gateway_response(response)

    def bootstrap_connector(
        self,
        *,
        username: str,
        password: str,
        client_ip: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> GatewayConnectorResponse:
        cid = correlation_id or new_correlation_id("iaai-gateway-bootstrap")
        logger.info(
            "iaai_gateway.bootstrap.start",
            extra=make_log_extra("iaai_gateway.bootstrap.start", correlation_id=cid),
        )
        client = self._client_factory()
        try:
            result = self._bootstrap_connector_session(
                client,
                username=username,
                password=password,
                client_ip=client_ip,
                correlation_id=cid,
            )
        except Exception as exc:
            diagnostics = exc.diagnostics if isinstance(exc, IaaiError) else None
            logger.warning(
                "iaai_gateway.bootstrap.failed",
                extra=make_log_extra(
                    "iaai_gateway.bootstrap.failed",
                    correlation_id=(diagnostics.correlation_id if diagnostics else None) or cid,
                    step=(diagnostics.step if diagnostics else None),
                    error_code=(diagnostics.error_code if diagnostics else None),
                    failure_class=(diagnostics.failure_class if diagnostics else None),
                    upstream_status_code=(diagnostics.upstream_status_code if diagnostics else None),
                    error_type=type(exc).__name__,
                ),
            )
            raise
        finally:
            client.close()
        raw_bundle = self._require_raw_bundle(result.bundle)
        logger.info(
            "iaai_gateway.bootstrap.success",
            extra=make_log_extra(
                "iaai_gateway.bootstrap.success",
                correlation_id=cid,
                status=result.connection_status,
            ),
        )
        return GatewayConnectorResponse(
            session_bundle=self._encrypt_session_bundle(raw_bundle),
            status=result.connection_status,
            verified_at=result.verified_at,
            account_label=result.account_label,
        )

    def verify_connector(self, session_bundle: IaaiEncryptedSessionBundle) -> GatewayConnectorResponse:
        client = self._client_factory()
        try:
            raw_bundle = self._decrypt_session_bundle(session_bundle)
            result = client.verify_connector_session(raw_bundle)
        finally:
            client.close()
        return self._to_connector_response(result)

    def execute_connector_search(
        self,
        session_bundle: IaaiEncryptedSessionBundle,
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
        session_bundle: IaaiEncryptedSessionBundle,
        *,
        provider_lot_id: str,
        etag: Optional[str] = None,
    ) -> GatewayConnectorResponse:
        client = self._client_factory()
        try:
            raw_bundle = self._decrypt_session_bundle(session_bundle)
            result = client.lot_details_with_connector_session(provider_lot_id, raw_bundle, etag=etag)
        finally:
            client.close()
        return self._to_connector_response(result)

    def _build_default_client(self) -> IaaiHttpClient:
        return IaaiHttpClient(settings=self._settings.model_copy(update={"iaai_gateway_base_url": None}))

    @staticmethod
    def _bootstrap_connector_session(client, *, username: str, password: str, client_ip: str | None, correlation_id: str):
        try:
            return client.bootstrap_connector_session(
                username=username,
                password=password,
                client_ip=client_ip,
                correlation_id=correlation_id,
            )
        except TypeError as exc:
            message = str(exc)
            if "correlation_id" in message and "client_ip" in message:
                return client.bootstrap_connector_session(username=username, password=password)
            if "correlation_id" in message:
                return client.bootstrap_connector_session(username=username, password=password, client_ip=client_ip)
            if "client_ip" in message:
                return client.bootstrap_connector_session(username=username, password=password, correlation_id=correlation_id)
            raise

    @staticmethod
    def _to_gateway_response(response: IaaiHttpPayloadResponse) -> GatewayProxyResponse:
        return GatewayProxyResponse(payload=response.payload, etag=response.etag, not_modified=response.not_modified)

    def _to_connector_response(self, response: IaaiConnectorExecutionResult) -> GatewayConnectorResponse:
        encrypted_bundle = None
        if response.bundle is not None:
            encrypted_bundle = self._encrypt_session_bundle(self._require_raw_bundle(response.bundle))
        return GatewayConnectorResponse(
            session_bundle=encrypted_bundle
            or IaaiEncryptedSessionBundle(
                encrypted_bundle="",
                key_version=self._settings.iaai_connector_encryption_key_version,
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

    def _encrypt_session_bundle(self, bundle: IaaiSessionBundle) -> IaaiEncryptedSessionBundle:
        cipher = self._build_fernet()
        captured_at = bundle.captured_at or datetime.now(timezone.utc)
        encrypted = cipher.encrypt(json.dumps(bundle.to_payload(), separators=(",", ":")).encode("utf-8")).decode("utf-8")
        return IaaiEncryptedSessionBundle(
            encrypted_bundle=encrypted,
            key_version=self._settings.iaai_connector_encryption_key_version,
            captured_at=captured_at,
            expires_at=bundle.expires_at,
        )

    def _decrypt_session_bundle(self, bundle: IaaiEncryptedSessionBundle) -> IaaiSessionBundle:
        cipher = self._build_fernet()
        try:
            payload = cipher.decrypt(bundle.encrypted_bundle.encode("utf-8"))
        except InvalidToken as exc:
            raise IaaiConfigurationError("IAAI connector session bundle could not be decrypted.") from exc
        return IaaiSessionBundle.from_payload(json.loads(payload.decode("utf-8")))

    @staticmethod
    def _require_raw_bundle(bundle: object) -> IaaiSessionBundle:
        if isinstance(bundle, IaaiSessionBundle):
            return bundle
        if isinstance(bundle, IaaiEncryptedSessionBundle):
            raw = base64.urlsafe_b64decode(bundle.encrypted_bundle.encode("ascii")).decode("utf-8")
            return IaaiSessionBundle.from_payload(json.loads(raw))
        raise IaaiConfigurationError("IAAI connector execution requires a serialized session bundle.")

    def _build_fernet(self) -> Fernet:
        key = self._settings.iaai_connector_encryption_key
        if not key:
            raise IaaiConfigurationError("IAAI_CONNECTOR_ENCRYPTION_KEY is not configured.")
        try:
            return Fernet(key.encode("utf-8"))
        except (TypeError, ValueError) as exc:
            raise IaaiConfigurationError("IAAI_CONNECTOR_ENCRYPTION_KEY is invalid.") from exc
