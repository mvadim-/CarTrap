from pathlib import Path
import sys

import httpx
import pytest
from pydantic import ValidationError


ROOT = Path(__file__).resolve().parents[2] / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from cartrap.config import Settings
from cartrap.modules.copart_provider.client import CopartHttpClient, reset_shared_http_client_pool
from cartrap.modules.copart_provider.errors import (
    CopartConfigurationError,
    CopartGatewayMalformedResponseError,
    CopartGatewayUnavailableError,
    CopartGatewayUpstreamError,
)


def make_base_settings(**overrides: object) -> Settings:
    payload = {
        "ENVIRONMENT": "test",
        "MONGO_URI": "mongodb://localhost:27017",
        "MONGO_DB": "cartrap_test",
        "MONGO_PING_ON_STARTUP": False,
        "COPART_API_DEVICE_NAME": "iPhone 15 Pro Max",
        "COPART_API_D_TOKEN": "token-123",
        "COPART_API_COOKIE": "SessionID=abc",
        "COPART_API_SITECODE": "CPRTUS",
    }
    payload.update(overrides)
    return Settings(**payload)


@pytest.fixture(autouse=True)
def clear_shared_http_clients() -> None:
    reset_shared_http_client_pool()
    yield
    reset_shared_http_client_pool()


def test_settings_enable_gateway_and_parse_transport_tuning() -> None:
    settings = make_base_settings(
        COPART_HTTP_TIMEOUT_SECONDS=19,
        COPART_HTTP_CONNECT_TIMEOUT_SECONDS=7,
        COPART_HTTP_KEEPALIVE_EXPIRY_SECONDS=55,
        COPART_HTTP_MAX_CONNECTIONS=24,
        COPART_HTTP_MAX_KEEPALIVE_CONNECTIONS=12,
        COPART_GATEWAY_BASE_URL="https://gateway.example.com",
        COPART_GATEWAY_TOKEN="secret-token",
        COPART_GATEWAY_ENABLE_GZIP=False,
    )

    assert settings.copart_gateway_enabled is True
    assert settings.copart_gateway_base_url == "https://gateway.example.com"
    assert settings.copart_gateway_token == "secret-token"
    assert settings.copart_gateway_enable_gzip is False
    assert settings.copart_http_timeout_seconds == 19
    assert settings.copart_http_connect_timeout_seconds == 7
    assert settings.copart_http_keepalive_expiry_seconds == 55
    assert settings.copart_http_max_connections == 24
    assert settings.copart_http_max_keepalive_connections == 12


def test_settings_require_gateway_token_when_base_url_is_configured() -> None:
    with pytest.raises(ValidationError, match="COPART_GATEWAY_TOKEN"):
        make_base_settings(COPART_GATEWAY_BASE_URL="https://gateway.example.com", COPART_GATEWAY_TOKEN=None)


def test_settings_allow_gateway_token_without_base_url_for_nas_gateway_runtime() -> None:
    settings = make_base_settings(COPART_GATEWAY_TOKEN="secret-token")

    assert settings.copart_gateway_token == "secret-token"
    assert settings.copart_gateway_base_url is None
    assert settings.copart_gateway_enabled is False


def test_settings_reject_keepalive_connections_above_total_connection_limit() -> None:
    with pytest.raises(ValidationError, match="COPART_HTTP_MAX_KEEPALIVE_CONNECTIONS"):
        make_base_settings(COPART_HTTP_MAX_CONNECTIONS=4, COPART_HTTP_MAX_KEEPALIVE_CONNECTIONS=5)


def test_client_uses_direct_transport_when_gateway_is_not_configured() -> None:
    client = CopartHttpClient(settings=make_base_settings())

    assert client.transport_mode == "direct"

    client.close()


def test_client_uses_gateway_transport_and_sends_bearer_auth_and_gzip_header() -> None:
    captured_headers: dict[str, str] = {}
    captured_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_headers.update(dict(request.headers))
        captured_urls.append(str(request.url))
        return httpx.Response(200, json={"response": {"docs": [], "numFound": 0}})

    client = CopartHttpClient(
        settings=make_base_settings(
            COPART_GATEWAY_BASE_URL="https://gateway.example.com",
            COPART_GATEWAY_TOKEN="secret-token",
        ),
        transport=httpx.MockTransport(handler),
    )

    response = client.search({"pageNumber": 1})

    assert client.transport_mode == "gateway"
    assert response["response"]["numFound"] == 0
    assert captured_urls == ["https://gateway.example.com/v1/search"]
    assert captured_headers["authorization"] == "Bearer secret-token"
    assert captured_headers["accept-encoding"] == "gzip"

    client.close()


def test_gateway_search_count_uses_dedicated_endpoint() -> None:
    captured_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_urls.append(str(request.url))
        return httpx.Response(200, json={"response": {"numFound": 5}})

    client = CopartHttpClient(
        settings=make_base_settings(
            COPART_GATEWAY_BASE_URL="https://gateway.example.com",
            COPART_GATEWAY_TOKEN="secret-token",
        ),
        transport=httpx.MockTransport(handler),
    )

    response = client.search_count_with_metadata({"pageNumber": 1})

    assert response.payload == {"response": {"numFound": 5}}
    assert captured_urls == ["https://gateway.example.com/v1/search-count"]

    client.close()


def test_client_raises_configuration_error_for_explicit_gateway_without_token() -> None:
    with pytest.raises(CopartConfigurationError, match="token is not configured"):
        CopartHttpClient(
            settings=make_base_settings(),
            gateway_base_url="https://gateway.example.com",
            gateway_token="",
        )


def test_gateway_maps_service_unavailable_to_gateway_unavailable_error() -> None:
    client = CopartHttpClient(
        settings=make_base_settings(
            COPART_GATEWAY_BASE_URL="https://gateway.example.com",
            COPART_GATEWAY_TOKEN="secret-token",
        ),
        transport=httpx.MockTransport(lambda request: httpx.Response(503)),
    )

    with pytest.raises(CopartGatewayUnavailableError, match="status 503"):
        client.search({"pageNumber": 1})

    client.close()


def test_gateway_maps_upstream_rejection_to_explicit_error_type() -> None:
    client = CopartHttpClient(
        settings=make_base_settings(
            COPART_GATEWAY_BASE_URL="https://gateway.example.com",
            COPART_GATEWAY_TOKEN="secret-token",
        ),
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                502,
                headers={
                    "x-copart-gateway-error": "upstream_rejected",
                    "x-copart-upstream-status": "403",
                },
            )
        ),
    )

    with pytest.raises(CopartGatewayUpstreamError) as exc_info:
        client.search({"pageNumber": 1})

    assert exc_info.value.upstream_status_code == 403
    client.close()


def test_gateway_maps_invalid_json_payload_to_malformed_response_error() -> None:
    client = CopartHttpClient(
        settings=make_base_settings(
            COPART_GATEWAY_BASE_URL="https://gateway.example.com",
            COPART_GATEWAY_TOKEN="secret-token",
        ),
        transport=httpx.MockTransport(lambda request: httpx.Response(200, text="not-json")),
    )

    with pytest.raises(CopartGatewayMalformedResponseError, match="invalid JSON"):
        client.search({"pageNumber": 1})

    client.close()


def test_clients_with_same_settings_reuse_shared_http_client_instance() -> None:
    settings = make_base_settings(
        COPART_GATEWAY_BASE_URL="https://gateway.example.com",
        COPART_GATEWAY_TOKEN="secret-token",
    )

    first = CopartHttpClient(settings=settings)
    second = CopartHttpClient(settings=settings)

    assert first.transport_mode == "gateway"
    assert second.transport_mode == "gateway"
    assert first._transport._client is second._transport._client  # type: ignore[attr-defined]

    first.close()
    second.close()
