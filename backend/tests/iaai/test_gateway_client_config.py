from pathlib import Path
import sys

import httpx
import pytest
from pydantic import ValidationError


ROOT = Path(__file__).resolve().parents[2] / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from cartrap.config import Settings
from cartrap.modules.iaai_provider.client import IaaiHttpClient
from cartrap.modules.iaai_provider.errors import (
    IaaiAuthenticationError,
    IaaiConfigurationError,
    IaaiGatewayMalformedResponseError,
    IaaiSessionInvalidError,
    IaaiWafError,
)


def make_base_settings(**overrides: object) -> Settings:
    payload = {
        "ENVIRONMENT": "test",
        "MONGO_URI": "mongodb://localhost:27017",
        "MONGO_DB": "cartrap_test",
        "MONGO_PING_ON_STARTUP": False,
        "IAAI_GATEWAY_BASE_URL": None,
        "IAAI_GATEWAY_TOKEN": None,
    }
    payload.update(overrides)
    return Settings(**payload)


def test_settings_enable_iaai_gateway() -> None:
    settings = make_base_settings(
        IAAI_GATEWAY_BASE_URL="https://gateway.example.com",
        IAAI_GATEWAY_TOKEN="secret-token",
        IAAI_GATEWAY_ENABLE_GZIP=False,
    )

    assert settings.iaai_gateway_enabled is True
    assert settings.iaai_gateway_base_url == "https://gateway.example.com"
    assert settings.iaai_gateway_token == "secret-token"
    assert settings.iaai_gateway_enable_gzip is False


def test_settings_require_iaai_gateway_token_when_base_url_is_configured() -> None:
    with pytest.raises(ValidationError, match="IAAI_GATEWAY_TOKEN"):
        make_base_settings(IAAI_GATEWAY_BASE_URL="https://gateway.example.com", IAAI_GATEWAY_TOKEN=None)


def test_client_uses_gateway_transport_when_configured() -> None:
    captured_headers: dict[str, str] = {}
    captured_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_headers.update(dict(request.headers))
        captured_urls.append(str(request.url))
        return httpx.Response(200, json={"vehicles": [], "totalCount": 0})

    client = IaaiHttpClient(
        settings=make_base_settings(
            IAAI_GATEWAY_BASE_URL="https://gateway.example.com",
            IAAI_GATEWAY_TOKEN="secret-token",
        ),
        transport=httpx.MockTransport(handler),
    )

    response = client.search({"pageNumber": 1})

    assert response == {"vehicles": [], "totalCount": 0}
    assert captured_urls == ["https://gateway.example.com/v1/search"]
    assert captured_headers["authorization"] == "Bearer secret-token"
    assert captured_headers["accept-encoding"] == "gzip"
    client.close()


def test_gateway_maps_explicit_connector_errors() -> None:
    def run_with_headers(headers: dict[str, str], expected_exception: type[Exception]) -> None:
        client = IaaiHttpClient(
            settings=make_base_settings(
                IAAI_GATEWAY_BASE_URL="https://gateway.example.com",
                IAAI_GATEWAY_TOKEN="secret-token",
            ),
            transport=httpx.MockTransport(lambda request: httpx.Response(502, headers=headers)),
        )
        with pytest.raises(expected_exception):
            client.bootstrap_connector_session(username="user@example.com", password="secret")
        client.close()

    run_with_headers({"x-iaai-gateway-error": "upstream_rejected"}, IaaiWafError)
    run_with_headers({"x-iaai-gateway-error": "invalid_credentials"}, IaaiAuthenticationError)
    run_with_headers({"x-iaai-gateway-error": "auth_invalid"}, IaaiSessionInvalidError)
    run_with_headers({"x-iaai-gateway-error": "malformed_response"}, IaaiGatewayMalformedResponseError)
