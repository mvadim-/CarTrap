"""Transport-aware Copart client facade for direct and gateway-backed requests."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Optional, Protocol

import httpx

from cartrap.config import Settings, get_settings
from cartrap.modules.copart_provider.errors import (
    CopartConfigurationError,
    CopartGatewayMalformedResponseError,
    CopartGatewayUnavailableError,
    CopartGatewayUpstreamError,
)

DEFAULT_HEADERS = {
    "Content-Type": "application/json; charset=utf-8",
    "Accept": "application/json, text/plain, */*",
    "User-Agent": "/4.5.4 (Macintosh; OS X/26.3.1) GCDHTTPRequest",
}
GATEWAY_SEARCH_PATH = "/v1/search"
GATEWAY_LOT_DETAILS_PATH = "/v1/lot-details"
GATEWAY_SEARCH_KEYWORDS_PATH = "/v1/search-keywords"
GATEWAY_ERROR_HEADER = "x-copart-gateway-error"
GATEWAY_UPSTREAM_STATUS_HEADER = "x-copart-upstream-status"


@dataclass
class CopartHttpPayloadResponse:
    payload: Optional[dict]
    etag: Optional[str]
    not_modified: bool = False


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
    def search_with_metadata(self, payload: dict, etag: Optional[str] = None) -> CopartHttpPayloadResponse: ...

    def search_count_with_metadata(self, payload: dict, etag: Optional[str] = None) -> CopartHttpPayloadResponse: ...

    def lot_details_with_metadata(self, lot_number: str, etag: Optional[str] = None) -> CopartHttpPayloadResponse: ...

    def search_keywords(self) -> dict: ...

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

    @property
    def mode(self) -> str:
        return "direct"

    def search_with_metadata(self, payload: dict, etag: Optional[str] = None) -> CopartHttpPayloadResponse:
        return self._request_json("POST", self._search_path, json=payload, etag=etag)

    def search_count_with_metadata(self, payload: dict, etag: Optional[str] = None) -> CopartHttpPayloadResponse:
        return self.search_with_metadata(payload, etag=etag)

    def lot_details_with_metadata(self, lot_number: str, etag: Optional[str] = None) -> CopartHttpPayloadResponse:
        return self._request_json("POST", self._lot_details_path, json={"lotNumber": int(lot_number)}, etag=etag)

    def search_keywords(self) -> dict:
        response = self._client.get(self._search_keywords_path, headers=self._auth_headers())
        response.raise_for_status()
        return response.json()

    def _auth_headers(self) -> dict[str, str]:
        if not self._device_name or not self._d_token or not self._cookie:
            raise CopartConfigurationError("Copart API credentials are not configured.")
        return {
            "devicename": self._device_name,
            "x-d-token": self._d_token,
            "Cookie": self._cookie,
            "sitecode": self._site_code,
        }

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        json: Optional[dict] = None,
        etag: Optional[str] = None,
    ) -> CopartHttpPayloadResponse:
        headers = self._auth_headers()
        if etag:
            headers["If-None-Match"] = etag
        response = self._client.request(method, path, json=json, headers=headers)
        if response.status_code == httpx.codes.NOT_MODIFIED:
            return CopartHttpPayloadResponse(payload=None, etag=response.headers.get("etag") or etag, not_modified=True)
        response.raise_for_status()
        return CopartHttpPayloadResponse(payload=response.json(), etag=response.headers.get("etag"), not_modified=False)


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

    def search_with_metadata(self, payload: dict, etag: Optional[str] = None) -> CopartHttpPayloadResponse:
        return self._request_json("POST", GATEWAY_SEARCH_PATH, json=payload, etag=etag)

    def search_count_with_metadata(self, payload: dict, etag: Optional[str] = None) -> CopartHttpPayloadResponse:
        return self._request_json("POST", "/v1/search-count", json=payload, etag=etag)

    def lot_details_with_metadata(self, lot_number: str, etag: Optional[str] = None) -> CopartHttpPayloadResponse:
        return self._request_json("POST", GATEWAY_LOT_DETAILS_PATH, json={"lotNumber": int(lot_number)}, etag=etag)

    def search_keywords(self) -> dict:
        return self._request_json("GET", GATEWAY_SEARCH_KEYWORDS_PATH).payload or {}

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        json: Optional[dict] = None,
        etag: Optional[str] = None,
    ) -> CopartHttpPayloadResponse:
        headers: dict[str, str] = {}
        if etag:
            headers["If-None-Match"] = etag

        try:
            response = self._client.request(method, path, json=json, headers=headers)
        except httpx.HTTPError as exc:
            raise CopartGatewayUnavailableError("Copart gateway is unavailable.") from exc

        if response.status_code == httpx.codes.NOT_MODIFIED:
            return CopartHttpPayloadResponse(payload=None, etag=response.headers.get("etag") or etag, not_modified=True)
        if response.is_error:
            self._raise_gateway_error(response)

        try:
            payload = response.json()
        except ValueError as exc:
            raise CopartGatewayMalformedResponseError("Copart gateway returned invalid JSON.") from exc

        if not isinstance(payload, dict):
            raise CopartGatewayMalformedResponseError("Copart gateway response must be a JSON object.")
        return CopartHttpPayloadResponse(payload=payload, etag=response.headers.get("etag"), not_modified=False)

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

    def search_with_metadata(self, payload: dict, etag: Optional[str] = None) -> CopartHttpPayloadResponse:
        return self._transport.search_with_metadata(payload, etag=etag)

    def search_count_with_metadata(self, payload: dict, etag: Optional[str] = None) -> CopartHttpPayloadResponse:
        return self._transport.search_count_with_metadata(payload, etag=etag)

    def lot_details(self, lot_number: str) -> dict:
        response = self.lot_details_with_metadata(lot_number)
        if response.not_modified or response.payload is None:
            raise RuntimeError("Lot details payload is not available for a 304 response.")
        return response.payload

    def lot_details_with_metadata(self, lot_number: str, etag: Optional[str] = None) -> CopartHttpPayloadResponse:
        return self._transport.lot_details_with_metadata(lot_number, etag=etag)

    def search_keywords(self) -> dict:
        return self._transport.search_keywords()

    def close(self) -> None:
        self._transport.close()
