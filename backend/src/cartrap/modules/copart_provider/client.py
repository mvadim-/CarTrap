"""Transport-aware Copart client facade for direct and gateway-backed requests."""

from __future__ import annotations

from datetime import datetime, timezone
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from http.cookies import SimpleCookie
import logging
from threading import Lock
from time import perf_counter
from typing import Any, Optional, Protocol
from uuid import uuid4

import httpx

from cartrap.config import Settings, get_settings
from cartrap.core.logging import make_log_extra, new_correlation_id
from cartrap.modules.copart_provider.errors import (
    CopartAuthenticationError,
    CopartChallengeError,
    CopartConfigurationError,
    CopartGatewayMalformedResponseError,
    CopartGatewayUnavailableError,
    CopartGatewayUpstreamError,
    CopartRateLimitError,
    CopartSessionInvalidError,
)
from cartrap.modules.provider_connections.models import STATUS_CONNECTED, STATUS_EXPIRING, STATUS_RECONNECT_REQUIRED

DEFAULT_HEADERS = {
    "Content-Type": "application/json; charset=utf-8",
    "Accept": "application/json, text/plain, */*",
    "User-Agent": "/4.5.4 (Macintosh; OS X/26.3.1) GCDHTTPRequest",
}
GATEWAY_SEARCH_PATH = "/v1/search"
GATEWAY_LOT_DETAILS_PATH = "/v1/lot-details"
GATEWAY_SEARCH_KEYWORDS_PATH = "/v1/search-keywords"
GATEWAY_CONNECTOR_BOOTSTRAP_PATH = "/v1/connector/bootstrap"
GATEWAY_CONNECTOR_VERIFY_PATH = "/v1/connector/verify"
GATEWAY_CONNECTOR_EXECUTE_SEARCH_PATH = "/v1/connector/execute/search"
GATEWAY_CONNECTOR_EXECUTE_LOT_DETAILS_PATH = "/v1/connector/execute/lot-details"
GATEWAY_ERROR_HEADER = "x-copart-gateway-error"
GATEWAY_UPSTREAM_STATUS_HEADER = "x-copart-upstream-status"
logger = logging.getLogger(__name__)


@dataclass
class CopartHttpPayloadResponse:
    payload: Optional[dict]
    etag: Optional[str]
    not_modified: bool = False


@dataclass(frozen=True)
class CopartHeaderProfile:
    device_name: str
    site_code: str
    company: str
    os: str
    language_code: str
    client_app_version: str
    user_agent: str

    def to_headers(self) -> dict[str, str]:
        return {
            "devicename": self.device_name,
            "sitecode": self.site_code,
            "company": self.company,
            "os": self.os,
            "languagecode": self.language_code,
            "clientappversion": self.client_app_version,
            "User-Agent": self.user_agent,
        }

    def to_payload(self) -> dict[str, str]:
        return {
            "device_name": self.device_name,
            "site_code": self.site_code,
            "company": self.company,
            "os": self.os,
            "language_code": self.language_code,
            "client_app_version": self.client_app_version,
            "user_agent": self.user_agent,
        }

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "CopartHeaderProfile":
        return cls(
            device_name=str(payload["device_name"]),
            site_code=str(payload["site_code"]),
            company=str(payload["company"]),
            os=str(payload["os"]),
            language_code=str(payload["language_code"]),
            client_app_version=str(payload["client_app_version"]),
            user_agent=str(payload["user_agent"]),
        )


@dataclass(frozen=True)
class CopartSessionBundle:
    session_id: str
    d_token: str
    device_id: str
    ins_sess: Optional[str]
    cookies: tuple[tuple[str, str], ...]
    header_profile: CopartHeaderProfile
    expires_at: Optional[datetime] = None
    captured_at: Optional[datetime] = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "d_token": self.d_token,
            "device_id": self.device_id,
            "ins_sess": self.ins_sess,
            "cookies": [{"name": name, "value": value} for name, value in self.cookies],
            "header_profile": self.header_profile.to_payload(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "captured_at": self.captured_at.isoformat() if self.captured_at else None,
        }

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "CopartSessionBundle":
        return cls(
            session_id=str(payload["session_id"]),
            d_token=str(payload["d_token"]),
            device_id=str(payload["device_id"]),
            ins_sess=(str(payload["ins_sess"]) if payload.get("ins_sess") else None),
            cookies=tuple((str(item["name"]), str(item["value"])) for item in payload.get("cookies", [])),
            header_profile=CopartHeaderProfile.from_payload(payload["header_profile"]),
            expires_at=_parse_optional_datetime(payload.get("expires_at")),
            captured_at=_parse_optional_datetime(payload.get("captured_at")),
        )

    def cookie_header(self) -> str:
        cookie_pairs = list(self.cookies)
        existing_names = {name for name, _ in cookie_pairs}
        if "SessionID" not in existing_names:
            cookie_pairs.append(("SessionID", self.session_id))
        if self.ins_sess and "ins-sess" not in existing_names:
            cookie_pairs.append(("ins-sess", self.ins_sess))
        return "; ".join(f"{name}={value}" for name, value in cookie_pairs if value)

    def auth_headers(self, etag: Optional[str] = None) -> dict[str, str]:
        headers = self.header_profile.to_headers()
        headers["x-d-token"] = self.d_token
        headers["Cookie"] = self.cookie_header()
        headers["deviceid"] = self.device_id
        if self.ins_sess:
            headers["ins-sess"] = self.ins_sess
        if etag:
            headers["If-None-Match"] = etag
        return headers

    @classmethod
    def from_http_response(
        cls,
        response: httpx.Response,
        *,
        header_profile: CopartHeaderProfile,
        existing: Optional["CopartSessionBundle"] = None,
        device_id: Optional[str] = None,
        fallback_d_token: Optional[str] = None,
    ) -> "CopartSessionBundle":
        cookie_map = {name: value for name, value in (existing.cookies if existing else ())}
        session_id = existing.session_id if existing is not None else ""
        ins_sess = existing.ins_sess if existing is not None else None
        expires_at = existing.expires_at if existing is not None else None
        for raw_cookie in response.headers.get_list("set-cookie"):
            parsed = SimpleCookie()
            parsed.load(raw_cookie)
            for morsel in parsed.values():
                cookie_map[morsel.key] = morsel.value
                if morsel.key == "SessionID":
                    session_id = morsel.value
                    if morsel["expires"]:
                        try:
                            expires_at = parsedate_to_datetime(morsel["expires"]).astimezone(timezone.utc)
                        except (TypeError, ValueError):
                            expires_at = expires_at
                elif morsel.key == "ins-sess":
                    ins_sess = morsel.value
        if not session_id:
            session_id = response.cookies.get("SessionID", session_id)
        if not ins_sess:
            ins_sess = response.cookies.get("ins-sess", ins_sess)
        d_token = (
            response.headers.get("x-d-token")
            or (existing.d_token if existing is not None else "")
            or (fallback_d_token or "")
        )
        resolved_device_id = device_id or (existing.device_id if existing is not None else "")
        if not session_id or not d_token or not resolved_device_id:
            raise CopartChallengeError("Session bundle is missing required login artifacts.")
        return cls(
            session_id=session_id,
            d_token=d_token,
            device_id=resolved_device_id,
            ins_sess=ins_sess,
            cookies=tuple(sorted(cookie_map.items())),
            header_profile=header_profile,
            expires_at=expires_at,
            captured_at=datetime.now(timezone.utc),
        )


@dataclass(frozen=True)
class CopartEncryptedSessionBundle:
    encrypted_bundle: str
    key_version: str
    captured_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "encrypted_bundle": self.encrypted_bundle,
            "key_version": self.key_version,
            "captured_at": self.captured_at.isoformat() if self.captured_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "CopartEncryptedSessionBundle":
        return cls(
            encrypted_bundle=str(payload["encrypted_bundle"]),
            key_version=str(payload["key_version"]),
            captured_at=_parse_optional_datetime(payload.get("captured_at")),
            expires_at=_parse_optional_datetime(payload.get("expires_at")),
        )


@dataclass
class CopartConnectorBootstrapResult:
    bundle: object
    account_label: Optional[str]
    connection_status: str
    verified_at: Optional[datetime]


@dataclass
class CopartConnectorExecutionResult:
    payload: Optional[dict]
    bundle: Optional[object]
    etag: Optional[str]
    not_modified: bool
    connection_status: str
    verified_at: Optional[datetime]
    used_at: Optional[datetime]


@dataclass(frozen=True)
class SharedHttpClientConfig:
    base_url: str
    timeout_seconds: float
    connect_timeout_seconds: float
    keepalive_expiry_seconds: float
    max_connections: int
    max_keepalive_connections: int
    default_headers: tuple[tuple[str, str], ...]
    follow_redirects: bool = True


class SharedHttpClientPool:
    """Caches httpx.Client instances so keep-alive survives per-request providers."""

    def __init__(self) -> None:
        self._clients: dict[SharedHttpClientConfig, httpx.Client] = {}
        self._lock = Lock()

    def get_or_create(self, config: SharedHttpClientConfig) -> httpx.Client:
        with self._lock:
            client = self._clients.get(config)
            if client is not None:
                return client

            client = httpx.Client(
                base_url=config.base_url,
                timeout=httpx.Timeout(config.timeout_seconds, connect=config.connect_timeout_seconds),
                headers=dict(config.default_headers),
                follow_redirects=config.follow_redirects,
                limits=httpx.Limits(
                    max_connections=config.max_connections,
                    max_keepalive_connections=config.max_keepalive_connections,
                    keepalive_expiry=config.keepalive_expiry_seconds,
                ),
            )
            self._clients[config] = client
            return client

    def clear(self) -> None:
        with self._lock:
            clients = list(self._clients.values())
            self._clients.clear()
        for client in clients:
            client.close()


_shared_http_client_pool = SharedHttpClientPool()


def reset_shared_http_client_pool() -> None:
    _shared_http_client_pool.clear()


class CopartTransport(Protocol):
    def search_with_metadata(
        self, payload: dict, etag: Optional[str] = None, correlation_id: Optional[str] = None
    ) -> CopartHttpPayloadResponse: ...

    def search_count_with_metadata(
        self, payload: dict, etag: Optional[str] = None, correlation_id: Optional[str] = None
    ) -> CopartHttpPayloadResponse: ...

    def lot_details_with_metadata(
        self, lot_number: str, etag: Optional[str] = None, correlation_id: Optional[str] = None
    ) -> CopartHttpPayloadResponse: ...

    def search_keywords(self, correlation_id: Optional[str] = None) -> dict: ...

    def bootstrap_connector_session(
        self,
        username: str,
        password: str,
        correlation_id: Optional[str] = None,
    ) -> CopartConnectorBootstrapResult: ...

    def verify_connector_session(
        self,
        bundle: object,
        correlation_id: Optional[str] = None,
    ) -> CopartConnectorExecutionResult: ...

    def search_with_connector_session(
        self,
        payload: dict,
        bundle: object,
        correlation_id: Optional[str] = None,
    ) -> CopartConnectorExecutionResult: ...

    def lot_details_with_connector_session(
        self,
        lot_number: str,
        bundle: object,
        etag: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> CopartConnectorExecutionResult: ...

    def close(self) -> None: ...

    @property
    def mode(self) -> str: ...


class _BaseHttpTransport:
    def __init__(
        self,
        *,
        client: Optional[httpx.Client] = None,
        transport: Optional[httpx.BaseTransport] = None,
        client_config: SharedHttpClientConfig,
    ) -> None:
        if client is not None:
            self._client = client
            self._owns_client = False
        elif transport is not None:
            self._client = httpx.Client(
                base_url=client_config.base_url,
                timeout=httpx.Timeout(client_config.timeout_seconds, connect=client_config.connect_timeout_seconds),
                headers=dict(client_config.default_headers),
                follow_redirects=client_config.follow_redirects,
                limits=httpx.Limits(
                    max_connections=client_config.max_connections,
                    max_keepalive_connections=client_config.max_keepalive_connections,
                    keepalive_expiry=client_config.keepalive_expiry_seconds,
                ),
                transport=transport,
            )
            self._owns_client = True
        else:
            self._client = _shared_http_client_pool.get_or_create(client_config)
            self._owns_client = False

    def close(self) -> None:
        if self._owns_client:
            self._client.close()


class DirectCopartTransport(_BaseHttpTransport):
    def __init__(
        self,
        *,
        settings: Settings,
        headers: Optional[dict[str, str]] = None,
        transport: Optional[httpx.BaseTransport] = None,
        client: Optional[httpx.Client] = None,
        base_url: Optional[str] = None,
        search_path: Optional[str] = None,
        search_keywords_path: Optional[str] = None,
        lot_details_path: Optional[str] = None,
        device_name: Optional[str] = None,
        d_token: Optional[str] = None,
        cookie: Optional[str] = None,
        site_code: Optional[str] = None,
    ) -> None:
        merged_headers = dict(DEFAULT_HEADERS)
        if headers:
            merged_headers.update(headers)
        super().__init__(
            client=client,
            transport=transport,
            client_config=SharedHttpClientConfig(
                base_url=base_url or settings.copart_api_base_url,
                timeout_seconds=settings.copart_http_timeout_seconds,
                connect_timeout_seconds=settings.copart_http_connect_timeout_seconds,
                keepalive_expiry_seconds=settings.copart_http_keepalive_expiry_seconds,
                max_connections=settings.copart_http_max_connections,
                max_keepalive_connections=settings.copart_http_max_keepalive_connections,
                default_headers=tuple(sorted(merged_headers.items())),
            ),
        )
        self._search_path = settings.copart_api_search_path if search_path is None else search_path
        self._search_keywords_path = (
            settings.copart_api_search_keywords_path if search_keywords_path is None else search_keywords_path
        )
        self._lot_details_path = settings.copart_api_lot_details_path if lot_details_path is None else lot_details_path
        self._device_name = settings.copart_api_device_name if device_name is None else device_name
        self._d_token = settings.copart_api_d_token if d_token is None else d_token
        self._cookie = settings.copart_api_cookie if cookie is None else cookie
        self._site_code = settings.copart_api_site_code if site_code is None else site_code
        self._settings = settings

    @property
    def mode(self) -> str:
        return "direct"

    def search_with_metadata(
        self, payload: dict, etag: Optional[str] = None, correlation_id: Optional[str] = None
    ) -> CopartHttpPayloadResponse:
        return self._request_json("POST", self._search_path, json=payload, etag=etag, correlation_id=correlation_id)

    def search_count_with_metadata(
        self, payload: dict, etag: Optional[str] = None, correlation_id: Optional[str] = None
    ) -> CopartHttpPayloadResponse:
        return self.search_with_metadata(payload, etag=etag, correlation_id=correlation_id)

    def lot_details_with_metadata(
        self, lot_number: str, etag: Optional[str] = None, correlation_id: Optional[str] = None
    ) -> CopartHttpPayloadResponse:
        return self._request_json(
            "POST",
            self._lot_details_path,
            json={"lotNumber": int(lot_number)},
            etag=etag,
            correlation_id=correlation_id,
        )

    def search_keywords(self, correlation_id: Optional[str] = None) -> dict:
        cid = correlation_id or new_correlation_id("copart-direct")
        started_at = perf_counter()
        logger.info(
            "copart_client.request.start",
            extra=make_log_extra(
                "copart_client.request.start",
                correlation_id=cid,
                transport_mode=self.mode,
                method="GET",
                path=self._search_keywords_path,
            ),
        )
        try:
            response = self._client.get(self._search_keywords_path, headers=self._auth_headers())
            response.raise_for_status()
            payload = response.json()
        except CopartConfigurationError:
            logger.exception(
                "copart_client.request.failed",
                extra=make_log_extra(
                    "copart_client.request.failed",
                    correlation_id=cid,
                    transport_mode=self.mode,
                    method="GET",
                    path=self._search_keywords_path,
                    failure_class="configuration_error",
                ),
            )
            raise
        except httpx.TimeoutException as exc:
            logger.warning(
                "copart_client.request.failed",
                extra=make_log_extra(
                    "copart_client.request.failed",
                    correlation_id=cid,
                    transport_mode=self.mode,
                    method="GET",
                    path=self._search_keywords_path,
                    duration_ms=round((perf_counter() - started_at) * 1000, 2),
                    failure_class="timeout",
                    error_type=type(exc).__name__,
                ),
            )
            raise
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "copart_client.request.failed",
                extra=make_log_extra(
                    "copart_client.request.failed",
                    correlation_id=cid,
                    transport_mode=self.mode,
                    method="GET",
                    path=self._search_keywords_path,
                    duration_ms=round((perf_counter() - started_at) * 1000, 2),
                    failure_class="upstream_http_error",
                    status_code=exc.response.status_code,
                ),
            )
            raise
        logger.info(
            "copart_client.request.success",
            extra=make_log_extra(
                "copart_client.request.success",
                correlation_id=cid,
                transport_mode=self.mode,
                method="GET",
                path=self._search_keywords_path,
                duration_ms=round((perf_counter() - started_at) * 1000, 2),
                status_code=response.status_code,
            ),
        )
        return payload

    def bootstrap_connector_session(
        self,
        username: str,
        password: str,
        correlation_id: Optional[str] = None,
    ) -> CopartConnectorBootstrapResult:
        cid = correlation_id or new_correlation_id("copart-bootstrap")
        profile = self._build_header_profile()
        device_id = uuid4().hex
        bootstrap_headers = profile.to_headers()
        bootstrap_headers["deviceid"] = device_id
        if self._settings.copart_api_d_token:
            bootstrap_headers["x-d-token"] = self._settings.copart_api_d_token
        if self._settings.copart_connector_bootstrap_path:
            self._client.get(self._settings.copart_connector_bootstrap_path, headers=bootstrap_headers)
        login_response = self._client.post(
            self._settings.copart_connector_login_path,
            json={"username": username, "password": password, "deviceId": device_id},
            headers=bootstrap_headers,
        )
        if login_response.status_code in {httpx.codes.UNAUTHORIZED, httpx.codes.FORBIDDEN}:
            raise CopartAuthenticationError("Copart rejected credentials.")
        login_response.raise_for_status()
        login_payload = _safe_json(login_response)
        bundle = CopartSessionBundle.from_http_response(
            login_response,
            header_profile=profile,
            existing=None,
            device_id=device_id,
            fallback_d_token=self._settings.copart_api_d_token,
        )
        if _response_requires_challenge(login_payload):
            challenge_payload = _build_challenge_payload(login_payload, device_id=device_id)
            if not self._settings.copart_connector_challenge_path or challenge_payload is None:
                raise CopartChallengeError("Copart challenge flow could not be replayed.")
            challenge_response = self._client.post(
                self._settings.copart_connector_challenge_path,
                json=challenge_payload,
                headers=bundle.auth_headers(),
            )
            if challenge_response.status_code in {httpx.codes.UNAUTHORIZED, httpx.codes.FORBIDDEN}:
                raise CopartChallengeError("Copart challenge flow was rejected.")
            challenge_response.raise_for_status()
            bundle = CopartSessionBundle.from_http_response(
                challenge_response,
                header_profile=profile,
                existing=bundle,
                device_id=device_id,
                fallback_d_token=self._settings.copart_api_d_token,
            )
        if self._settings.copart_connector_identity_path:
            identity_response = self._client.get(
                self._settings.copart_connector_identity_path,
                headers=bundle.auth_headers(),
            )
            identity_response.raise_for_status()
            bundle = CopartSessionBundle.from_http_response(
                identity_response,
                header_profile=profile,
                existing=bundle,
                device_id=device_id,
                fallback_d_token=self._settings.copart_api_d_token,
            )
        verification = self.verify_connector_session(bundle, correlation_id=cid)
        return CopartConnectorBootstrapResult(
            bundle=bundle,
            account_label=_extract_account_label(login_payload),
            connection_status=verification.connection_status,
            verified_at=verification.verified_at,
        )

    def verify_connector_session(
        self,
        bundle: object,
        correlation_id: Optional[str] = None,
    ) -> CopartConnectorExecutionResult:
        resolved_bundle = _require_session_bundle(bundle)
        verify_path = self._settings.copart_connector_verify_path
        if not verify_path:
            return CopartConnectorExecutionResult(
                payload=None,
                bundle=resolved_bundle,
                etag=None,
                not_modified=False,
                connection_status=_connection_status_for_expiry(
                    resolved_bundle.expires_at,
                    self._settings.copart_connector_session_expiring_threshold_minutes,
                ),
                verified_at=datetime.now(timezone.utc),
                used_at=datetime.now(timezone.utc),
            )
        response = self._client.get(verify_path, headers=resolved_bundle.auth_headers())
        if response.status_code in {httpx.codes.UNAUTHORIZED, httpx.codes.FORBIDDEN}:
            raise CopartSessionInvalidError("Copart session is no longer valid.")
        response.raise_for_status()
        rotated_bundle = CopartSessionBundle.from_http_response(
            response,
            header_profile=resolved_bundle.header_profile,
            existing=resolved_bundle,
            device_id=resolved_bundle.device_id,
            fallback_d_token=self._settings.copart_api_d_token,
        )
        used_at = datetime.now(timezone.utc)
        return CopartConnectorExecutionResult(
            payload=_safe_json(response),
            bundle=rotated_bundle,
            etag=response.headers.get("etag"),
            not_modified=False,
            connection_status=_connection_status_for_expiry(
                rotated_bundle.expires_at,
                self._settings.copart_connector_session_expiring_threshold_minutes,
            ),
            verified_at=used_at,
            used_at=used_at,
        )

    def search_with_connector_session(
        self,
        payload: dict,
        bundle: object,
        correlation_id: Optional[str] = None,
    ) -> CopartConnectorExecutionResult:
        del correlation_id
        resolved_bundle = _require_session_bundle(bundle)
        response = self._client.post(self._search_path, json=payload, headers=resolved_bundle.auth_headers())
        if response.status_code in {httpx.codes.UNAUTHORIZED, httpx.codes.FORBIDDEN}:
            raise CopartSessionInvalidError("Copart session is no longer valid.")
        response.raise_for_status()
        rotated_bundle = CopartSessionBundle.from_http_response(
            response,
            header_profile=resolved_bundle.header_profile,
            existing=resolved_bundle,
            device_id=resolved_bundle.device_id,
            fallback_d_token=self._settings.copart_api_d_token,
        )
        used_at = datetime.now(timezone.utc)
        return CopartConnectorExecutionResult(
            payload=response.json(),
            bundle=rotated_bundle,
            etag=response.headers.get("etag"),
            not_modified=False,
            connection_status=_connection_status_for_expiry(
                rotated_bundle.expires_at,
                self._settings.copart_connector_session_expiring_threshold_minutes,
            ),
            verified_at=used_at,
            used_at=used_at,
        )

    def lot_details_with_connector_session(
        self,
        lot_number: str,
        bundle: object,
        etag: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> CopartConnectorExecutionResult:
        del correlation_id
        resolved_bundle = _require_session_bundle(bundle)
        response = self._client.post(
            self._lot_details_path,
            json={"lotNumber": int(lot_number)},
            headers=resolved_bundle.auth_headers(etag=etag),
        )
        if response.status_code in {httpx.codes.UNAUTHORIZED, httpx.codes.FORBIDDEN}:
            raise CopartSessionInvalidError("Copart session is no longer valid.")
        if response.status_code == httpx.codes.NOT_MODIFIED:
            return CopartConnectorExecutionResult(
                payload=None,
                bundle=resolved_bundle,
                etag=response.headers.get("etag") or etag,
                not_modified=True,
                connection_status=_connection_status_for_expiry(
                    resolved_bundle.expires_at,
                    self._settings.copart_connector_session_expiring_threshold_minutes,
                ),
                verified_at=datetime.now(timezone.utc),
                used_at=datetime.now(timezone.utc),
            )
        response.raise_for_status()
        rotated_bundle = CopartSessionBundle.from_http_response(
            response,
            header_profile=resolved_bundle.header_profile,
            existing=resolved_bundle,
            device_id=resolved_bundle.device_id,
            fallback_d_token=self._settings.copart_api_d_token,
        )
        used_at = datetime.now(timezone.utc)
        return CopartConnectorExecutionResult(
            payload=response.json(),
            bundle=rotated_bundle,
            etag=response.headers.get("etag"),
            not_modified=False,
            connection_status=_connection_status_for_expiry(
                rotated_bundle.expires_at,
                self._settings.copart_connector_session_expiring_threshold_minutes,
            ),
            verified_at=used_at,
            used_at=used_at,
        )

    def _auth_headers(self) -> dict[str, str]:
        if not self._device_name or not self._d_token or not self._cookie:
            raise CopartConfigurationError("Copart API credentials are not configured.")
        return {
            "devicename": self._device_name,
            "x-d-token": self._d_token,
            "Cookie": self._cookie,
            "sitecode": self._site_code,
        }

    def _build_header_profile(self) -> CopartHeaderProfile:
        return CopartHeaderProfile(
            device_name=self._device_name or self._settings.copart_api_device_name or "iPhone",
            site_code=self._site_code or self._settings.copart_api_site_code,
            company=self._settings.copart_connector_mobile_company,
            os=self._settings.copart_connector_mobile_os,
            language_code=self._settings.copart_connector_mobile_language_code,
            client_app_version=self._settings.copart_connector_mobile_client_app_version,
            user_agent=DEFAULT_HEADERS["User-Agent"],
        )

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        json: Optional[dict] = None,
        etag: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> CopartHttpPayloadResponse:
        cid = correlation_id or new_correlation_id("copart-direct")
        started_at = perf_counter()
        logger.info(
            "copart_client.request.start",
            extra=make_log_extra(
                "copart_client.request.start",
                correlation_id=cid,
                transport_mode=self.mode,
                method=method,
                path=path,
                has_etag=bool(etag),
            ),
        )
        try:
            headers = self._auth_headers()
            if etag:
                headers["If-None-Match"] = etag
            response = self._client.request(method, path, json=json, headers=headers)
            if response.status_code == httpx.codes.NOT_MODIFIED:
                logger.info(
                    "copart_client.request.success",
                    extra=make_log_extra(
                        "copart_client.request.success",
                        correlation_id=cid,
                        transport_mode=self.mode,
                        method=method,
                        path=path,
                        duration_ms=round((perf_counter() - started_at) * 1000, 2),
                        status_code=response.status_code,
                        outcome="not_modified",
                    ),
                )
                return CopartHttpPayloadResponse(
                    payload=None,
                    etag=response.headers.get("etag") or etag,
                    not_modified=True,
                )
            response.raise_for_status()
            payload = response.json()
        except CopartConfigurationError:
            logger.exception(
                "copart_client.request.failed",
                extra=make_log_extra(
                    "copart_client.request.failed",
                    correlation_id=cid,
                    transport_mode=self.mode,
                    method=method,
                    path=path,
                    failure_class="configuration_error",
                ),
            )
            raise
        except httpx.TimeoutException as exc:
            logger.warning(
                "copart_client.request.failed",
                extra=make_log_extra(
                    "copart_client.request.failed",
                    correlation_id=cid,
                    transport_mode=self.mode,
                    method=method,
                    path=path,
                    duration_ms=round((perf_counter() - started_at) * 1000, 2),
                    failure_class="timeout",
                    error_type=type(exc).__name__,
                ),
            )
            raise
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "copart_client.request.failed",
                extra=make_log_extra(
                    "copart_client.request.failed",
                    correlation_id=cid,
                    transport_mode=self.mode,
                    method=method,
                    path=path,
                    duration_ms=round((perf_counter() - started_at) * 1000, 2),
                    failure_class="upstream_http_error",
                    status_code=exc.response.status_code,
                ),
            )
            raise
        except httpx.HTTPError as exc:
            logger.warning(
                "copart_client.request.failed",
                extra=make_log_extra(
                    "copart_client.request.failed",
                    correlation_id=cid,
                    transport_mode=self.mode,
                    method=method,
                    path=path,
                    duration_ms=round((perf_counter() - started_at) * 1000, 2),
                    failure_class="transport_error",
                    error_type=type(exc).__name__,
                ),
            )
            raise
        logger.info(
            "copart_client.request.success",
            extra=make_log_extra(
                "copart_client.request.success",
                correlation_id=cid,
                transport_mode=self.mode,
                method=method,
                path=path,
                duration_ms=round((perf_counter() - started_at) * 1000, 2),
                status_code=response.status_code,
                outcome="refreshed",
            ),
        )
        return CopartHttpPayloadResponse(payload=payload, etag=response.headers.get("etag"), not_modified=False)


class GatewayCopartTransport(_BaseHttpTransport):
    def __init__(
        self,
        *,
        settings: Settings,
        headers: Optional[dict[str, str]] = None,
        transport: Optional[httpx.BaseTransport] = None,
        client: Optional[httpx.Client] = None,
        base_url: Optional[str] = None,
        gateway_token: Optional[str] = None,
        enable_gzip: Optional[bool] = None,
    ) -> None:
        resolved_base_url = base_url or settings.copart_gateway_base_url
        resolved_token = gateway_token if gateway_token is not None else settings.copart_gateway_token
        resolved_enable_gzip = settings.copart_gateway_enable_gzip if enable_gzip is None else enable_gzip
        if not resolved_base_url:
            raise CopartConfigurationError("Copart gateway base URL is not configured.")
        if not resolved_token:
            raise CopartConfigurationError("Copart gateway token is not configured.")

        merged_headers = dict(DEFAULT_HEADERS)
        merged_headers["Authorization"] = f"Bearer {resolved_token}"
        if resolved_enable_gzip:
            merged_headers["Accept-Encoding"] = "gzip"
        if headers:
            merged_headers.update(headers)

        super().__init__(
            client=client,
            transport=transport,
            client_config=SharedHttpClientConfig(
                base_url=resolved_base_url,
                timeout_seconds=settings.copart_http_timeout_seconds,
                connect_timeout_seconds=settings.copart_http_connect_timeout_seconds,
                keepalive_expiry_seconds=settings.copart_http_keepalive_expiry_seconds,
                max_connections=settings.copart_http_max_connections,
                max_keepalive_connections=settings.copart_http_max_keepalive_connections,
                default_headers=tuple(sorted(merged_headers.items())),
            ),
        )

    @property
    def mode(self) -> str:
        return "gateway"

    def search_with_metadata(
        self, payload: dict, etag: Optional[str] = None, correlation_id: Optional[str] = None
    ) -> CopartHttpPayloadResponse:
        return self._request_json("POST", GATEWAY_SEARCH_PATH, json=payload, etag=etag, correlation_id=correlation_id)

    def search_count_with_metadata(
        self, payload: dict, etag: Optional[str] = None, correlation_id: Optional[str] = None
    ) -> CopartHttpPayloadResponse:
        return self._request_json(
            "POST",
            "/v1/search-count",
            json=payload,
            etag=etag,
            correlation_id=correlation_id,
        )

    def lot_details_with_metadata(
        self, lot_number: str, etag: Optional[str] = None, correlation_id: Optional[str] = None
    ) -> CopartHttpPayloadResponse:
        return self._request_json(
            "POST",
            GATEWAY_LOT_DETAILS_PATH,
            json={"lotNumber": int(lot_number)},
            etag=etag,
            correlation_id=correlation_id,
        )

    def search_keywords(self, correlation_id: Optional[str] = None) -> dict:
        return self._request_json("GET", GATEWAY_SEARCH_KEYWORDS_PATH, correlation_id=correlation_id).payload or {}

    def bootstrap_connector_session(
        self,
        username: str,
        password: str,
        correlation_id: Optional[str] = None,
    ) -> CopartConnectorBootstrapResult:
        response = self._request_connector_json(
            "POST",
            GATEWAY_CONNECTOR_BOOTSTRAP_PATH,
            json={"username": username, "password": password},
            correlation_id=correlation_id,
        )
        payload = response.payload or {}
        return CopartConnectorBootstrapResult(
            bundle=CopartEncryptedSessionBundle.from_payload(payload["session_bundle"]),
            account_label=payload.get("account_label"),
            connection_status=str(payload.get("status") or STATUS_CONNECTED),
            verified_at=_parse_optional_datetime(payload.get("verified_at")),
        )

    def verify_connector_session(
        self,
        bundle: object,
        correlation_id: Optional[str] = None,
    ) -> CopartConnectorExecutionResult:
        response = self._request_connector_json(
            "POST",
            GATEWAY_CONNECTOR_VERIFY_PATH,
            json={"session_bundle": _require_encrypted_bundle(bundle).to_payload()},
            correlation_id=correlation_id,
        )
        return _parse_connector_execution_response(response.payload or {}, etag=response.etag, not_modified=response.not_modified)

    def search_with_connector_session(
        self,
        payload: dict,
        bundle: object,
        correlation_id: Optional[str] = None,
    ) -> CopartConnectorExecutionResult:
        response = self._request_connector_json(
            "POST",
            GATEWAY_CONNECTOR_EXECUTE_SEARCH_PATH,
            json={"session_bundle": _require_encrypted_bundle(bundle).to_payload(), "search_payload": payload},
            correlation_id=correlation_id,
        )
        return _parse_connector_execution_response(response.payload or {}, etag=response.etag, not_modified=response.not_modified)

    def lot_details_with_connector_session(
        self,
        lot_number: str,
        bundle: object,
        etag: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> CopartConnectorExecutionResult:
        response = self._request_connector_json(
            "POST",
            GATEWAY_CONNECTOR_EXECUTE_LOT_DETAILS_PATH,
            json={
                "session_bundle": _require_encrypted_bundle(bundle).to_payload(),
                "lot_number": int(lot_number),
            },
            etag=etag,
            correlation_id=correlation_id,
        )
        return _parse_connector_execution_response(response.payload or {}, etag=response.etag, not_modified=response.not_modified)

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        json: Optional[dict] = None,
        etag: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> CopartHttpPayloadResponse:
        cid = correlation_id or new_correlation_id("copart-gateway")
        started_at = perf_counter()
        logger.info(
            "copart_client.request.start",
            extra=make_log_extra(
                "copart_client.request.start",
                correlation_id=cid,
                transport_mode=self.mode,
                method=method,
                path=path,
                has_etag=bool(etag),
            ),
        )
        headers: dict[str, str] = {}
        if etag:
            headers["If-None-Match"] = etag

        try:
            response = self._client.request(method, path, json=json, headers=headers)
        except httpx.TimeoutException as exc:
            logger.warning(
                "copart_client.request.failed",
                extra=make_log_extra(
                    "copart_client.request.failed",
                    correlation_id=cid,
                    transport_mode=self.mode,
                    method=method,
                    path=path,
                    duration_ms=round((perf_counter() - started_at) * 1000, 2),
                    failure_class="timeout",
                    error_type=type(exc).__name__,
                ),
            )
            raise CopartGatewayUnavailableError("Copart gateway is unavailable.") from exc
        except httpx.HTTPError as exc:
            logger.warning(
                "copart_client.request.failed",
                extra=make_log_extra(
                    "copart_client.request.failed",
                    correlation_id=cid,
                    transport_mode=self.mode,
                    method=method,
                    path=path,
                    duration_ms=round((perf_counter() - started_at) * 1000, 2),
                    failure_class="transport_error",
                    error_type=type(exc).__name__,
                ),
            )
            raise CopartGatewayUnavailableError("Copart gateway is unavailable.") from exc

        if response.status_code == httpx.codes.NOT_MODIFIED:
            logger.info(
                "copart_client.request.success",
                extra=make_log_extra(
                    "copart_client.request.success",
                    correlation_id=cid,
                    transport_mode=self.mode,
                    method=method,
                    path=path,
                    duration_ms=round((perf_counter() - started_at) * 1000, 2),
                    status_code=response.status_code,
                    outcome="not_modified",
                ),
            )
            return CopartHttpPayloadResponse(payload=None, etag=response.headers.get("etag") or etag, not_modified=True)
        if response.is_error:
            gateway_error = (response.headers.get(GATEWAY_ERROR_HEADER) or "").strip().lower()
            failure_class = (
                "upstream_rejected"
                if gateway_error == "upstream_rejected"
                else "malformed_response"
                if gateway_error == "malformed_response"
                else "gateway_unavailable"
            )
            logger.warning(
                "copart_client.request.failed",
                extra=make_log_extra(
                    "copart_client.request.failed",
                    correlation_id=cid,
                    transport_mode=self.mode,
                    method=method,
                    path=path,
                    duration_ms=round((perf_counter() - started_at) * 1000, 2),
                    failure_class=failure_class,
                    status_code=response.status_code,
                    upstream_status=response.headers.get(GATEWAY_UPSTREAM_STATUS_HEADER),
                ),
            )
            self._raise_gateway_error(response)

        try:
            payload = response.json()
        except ValueError as exc:
            logger.warning(
                "copart_client.request.failed",
                extra=make_log_extra(
                    "copart_client.request.failed",
                    correlation_id=cid,
                    transport_mode=self.mode,
                    method=method,
                    path=path,
                    duration_ms=round((perf_counter() - started_at) * 1000, 2),
                    failure_class="invalid_json",
                ),
            )
            raise CopartGatewayMalformedResponseError("Copart gateway returned invalid JSON.") from exc

        if not isinstance(payload, dict):
            logger.warning(
                "copart_client.request.failed",
                extra=make_log_extra(
                    "copart_client.request.failed",
                    correlation_id=cid,
                    transport_mode=self.mode,
                    method=method,
                    path=path,
                    duration_ms=round((perf_counter() - started_at) * 1000, 2),
                    failure_class="non_object_json",
                ),
            )
            raise CopartGatewayMalformedResponseError("Copart gateway response must be a JSON object.")
        logger.info(
            "copart_client.request.success",
            extra=make_log_extra(
                "copart_client.request.success",
                correlation_id=cid,
                transport_mode=self.mode,
                method=method,
                path=path,
                duration_ms=round((perf_counter() - started_at) * 1000, 2),
                status_code=response.status_code,
                outcome="refreshed",
            ),
        )
        return CopartHttpPayloadResponse(payload=payload, etag=response.headers.get("etag"), not_modified=False)

    def _request_connector_json(
        self,
        method: str,
        path: str,
        *,
        json: Optional[dict] = None,
        etag: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> CopartHttpPayloadResponse:
        response = self._request_json(method, path, json=json, etag=etag, correlation_id=correlation_id)
        return response

    @staticmethod
    def _raise_gateway_error(response: httpx.Response) -> None:
        gateway_error = (response.headers.get(GATEWAY_ERROR_HEADER) or "").strip().lower()
        upstream_status_code: Optional[int] = None
        raw_upstream_status = response.headers.get(GATEWAY_UPSTREAM_STATUS_HEADER)
        if raw_upstream_status and raw_upstream_status.isdigit():
            upstream_status_code = int(raw_upstream_status)

        if gateway_error == "upstream_rejected":
            raise CopartGatewayUpstreamError(
                f"Copart gateway reported upstream rejection with status {upstream_status_code or response.status_code}.",
                upstream_status_code=upstream_status_code,
            )
        if gateway_error == "invalid_credentials":
            raise CopartAuthenticationError("Copart credentials were rejected.")
        if gateway_error == "auth_invalid":
            raise CopartSessionInvalidError("Copart session is no longer valid.")
        if gateway_error == "challenge_failed":
            raise CopartChallengeError("Copart challenge replay failed.")
        if gateway_error == "rate_limited":
            raise CopartRateLimitError("Copart connector bootstrap rate limited.")
        if gateway_error == "malformed_response":
            raise CopartGatewayMalformedResponseError("Copart gateway returned a malformed upstream response.")
        raise CopartGatewayUnavailableError(f"Copart gateway request failed with status {response.status_code}.")


class CopartHttpClient:
    def __init__(
        self,
        timeout_seconds: Optional[float] = None,
        headers: Optional[dict[str, str]] = None,
        transport: Optional[httpx.BaseTransport] = None,
        base_url: Optional[str] = None,
        search_path: Optional[str] = None,
        search_keywords_path: Optional[str] = None,
        lot_details_path: Optional[str] = None,
        device_name: Optional[str] = None,
        d_token: Optional[str] = None,
        cookie: Optional[str] = None,
        site_code: Optional[str] = None,
        settings: Optional[Settings] = None,
        gateway_base_url: Optional[str] = None,
        gateway_token: Optional[str] = None,
        gateway_enable_gzip: Optional[bool] = None,
        client: Optional[httpx.Client] = None,
    ) -> None:
        resolved_settings = settings or get_settings()
        if timeout_seconds is not None:
            resolved_settings = resolved_settings.model_copy(update={"copart_http_timeout_seconds": timeout_seconds})

        if gateway_base_url is not None or gateway_token is not None:
            resolved_settings = resolved_settings.model_copy(
                update={
                    "copart_gateway_base_url": gateway_base_url,
                    "copart_gateway_token": gateway_token,
                    "copart_gateway_enable_gzip": (
                        resolved_settings.copart_gateway_enable_gzip
                        if gateway_enable_gzip is None
                        else gateway_enable_gzip
                    ),
                }
            )
        elif gateway_enable_gzip is not None:
            resolved_settings = resolved_settings.model_copy(update={"copart_gateway_enable_gzip": gateway_enable_gzip})

        if resolved_settings.copart_gateway_enabled:
            self._transport: CopartTransport = GatewayCopartTransport(
                settings=resolved_settings,
                headers=headers,
                transport=transport,
                client=client,
                base_url=resolved_settings.copart_gateway_base_url,
                gateway_token=resolved_settings.copart_gateway_token,
                enable_gzip=resolved_settings.copart_gateway_enable_gzip,
            )
        else:
            self._transport = DirectCopartTransport(
                settings=resolved_settings,
                headers=headers,
                transport=transport,
                client=client,
                base_url=base_url,
                search_path=search_path,
                search_keywords_path=search_keywords_path,
                lot_details_path=lot_details_path,
                device_name=device_name,
                d_token=d_token,
                cookie=cookie,
                site_code=site_code,
            )

    @property
    def transport_mode(self) -> str:
        return self._transport.mode

    def search(self, payload: dict) -> dict:
        response = self.search_with_metadata(payload)
        if response.not_modified or response.payload is None:
            raise RuntimeError("Search payload is not available for a 304 response.")
        return response.payload

    def search_with_metadata(
        self, payload: dict, etag: Optional[str] = None, correlation_id: Optional[str] = None
    ) -> CopartHttpPayloadResponse:
        return self._transport.search_with_metadata(payload, etag=etag, correlation_id=correlation_id)

    def search_count_with_metadata(
        self, payload: dict, etag: Optional[str] = None, correlation_id: Optional[str] = None
    ) -> CopartHttpPayloadResponse:
        return self._transport.search_count_with_metadata(payload, etag=etag, correlation_id=correlation_id)

    def lot_details(self, lot_number: str) -> dict:
        response = self.lot_details_with_metadata(lot_number)
        if response.not_modified or response.payload is None:
            raise RuntimeError("Lot details payload is not available for a 304 response.")
        return response.payload

    def lot_details_with_metadata(
        self, lot_number: str, etag: Optional[str] = None, correlation_id: Optional[str] = None
    ) -> CopartHttpPayloadResponse:
        return self._transport.lot_details_with_metadata(lot_number, etag=etag, correlation_id=correlation_id)

    def search_keywords(self, correlation_id: Optional[str] = None) -> dict:
        return self._transport.search_keywords(correlation_id=correlation_id)

    def bootstrap_connector_session(
        self,
        *,
        username: str,
        password: str,
        correlation_id: Optional[str] = None,
    ) -> CopartConnectorBootstrapResult:
        return self._transport.bootstrap_connector_session(username, password, correlation_id=correlation_id)

    def verify_connector_session(
        self,
        bundle: object,
        correlation_id: Optional[str] = None,
    ) -> CopartConnectorExecutionResult:
        return self._transport.verify_connector_session(bundle, correlation_id=correlation_id)

    def search_with_connector_session(
        self,
        payload: dict,
        bundle: object,
        correlation_id: Optional[str] = None,
    ) -> CopartConnectorExecutionResult:
        return self._transport.search_with_connector_session(payload, bundle, correlation_id=correlation_id)

    def lot_details_with_connector_session(
        self,
        lot_number: str,
        bundle: object,
        etag: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> CopartConnectorExecutionResult:
        return self._transport.lot_details_with_connector_session(
            lot_number,
            bundle,
            etag=etag,
            correlation_id=correlation_id,
        )

    def close(self) -> None:
        self._transport.close()


def _parse_optional_datetime(value: Any) -> Optional[datetime]:
    if value in {None, ""}:
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc)
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)


def _response_requires_challenge(payload: dict[str, Any]) -> bool:
    return bool(payload.get("challengeRequired") or payload.get("requiresChallenge") or payload.get("challenge_required"))


def _build_challenge_payload(payload: dict[str, Any], *, device_id: str) -> Optional[dict[str, Any]]:
    challenge_token = payload.get("challengeToken") or payload.get("challenge_token")
    if not challenge_token:
        return None
    challenge_payload = {"challengeToken": challenge_token, "deviceId": device_id}
    if payload.get("challengeContext") is not None:
        challenge_payload["challengeContext"] = payload["challengeContext"]
    return challenge_payload


def _safe_json(response: httpx.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _extract_account_label(payload: dict[str, Any]) -> Optional[str]:
    candidate = payload.get("email") or payload.get("username") or payload.get("userName")
    if candidate is None:
        return None
    return str(candidate)


def _connection_status_for_expiry(expires_at: Optional[datetime], threshold_minutes: int) -> str:
    if expires_at is None:
        return STATUS_CONNECTED
    now = datetime.now(timezone.utc)
    if expires_at <= now:
        return STATUS_RECONNECT_REQUIRED
    if (expires_at - now).total_seconds() <= threshold_minutes * 60:
        return STATUS_EXPIRING
    return STATUS_CONNECTED


def _require_session_bundle(bundle: object) -> CopartSessionBundle:
    if not isinstance(bundle, CopartSessionBundle):
        raise CopartConfigurationError("Direct connector execution requires a raw Copart session bundle.")
    return bundle


def _require_encrypted_bundle(bundle: object) -> CopartEncryptedSessionBundle:
    if not isinstance(bundle, CopartEncryptedSessionBundle):
        raise CopartConfigurationError("Gateway connector execution requires an encrypted session bundle.")
    return bundle


def _parse_connector_execution_response(payload: dict[str, Any], *, etag: Optional[str], not_modified: bool) -> CopartConnectorExecutionResult:
    session_bundle_payload = payload.get("session_bundle")
    return CopartConnectorExecutionResult(
        payload=payload.get("payload"),
        bundle=CopartEncryptedSessionBundle.from_payload(session_bundle_payload) if isinstance(session_bundle_payload, dict) else None,
        etag=etag,
        not_modified=not_modified,
        connection_status=str(payload.get("status") or STATUS_CONNECTED),
        verified_at=_parse_optional_datetime(payload.get("verified_at")),
        used_at=_parse_optional_datetime(payload.get("used_at")),
    )
