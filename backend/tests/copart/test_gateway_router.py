from pathlib import Path
import sys
import json
import logging

import httpx
from fastapi.testclient import TestClient
import pytest


ROOT = Path(__file__).resolve().parents[2] / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from cartrap.config import Settings
from cartrap.gateway_app import create_gateway_app
from cartrap.modules.copart_gateway.service import CopartGatewayService
from cartrap.modules.copart_provider.client import CopartHttpClient


def make_gateway_settings(**overrides: object) -> Settings:
    payload = {
        "ENVIRONMENT": "test",
        "APP_NAME": "CarTrap Gateway Test",
        "MONGO_URI": "mongodb://unused",
        "MONGO_DB": "cartrap_test",
        "COPART_GATEWAY_BASE_URL": None,
        "COPART_GATEWAY_TOKEN": "gateway-secret",
        "COPART_API_DEVICE_NAME": "iPhone 15 Pro Max",
        "COPART_API_D_TOKEN": "token-123",
        "COPART_API_COOKIE": "SessionID=abc",
        "COPART_API_SITECODE": "CPRTUS",
    }
    payload.update(overrides)
    return Settings(**payload)


def make_gateway_client(settings: Settings, handler) -> CopartHttpClient:
    return CopartHttpClient(
        settings=settings.model_copy(update={"copart_gateway_base_url": None}),
        transport=httpx.MockTransport(handler),
    )


@pytest.fixture
def client() -> TestClient:
    app = create_gateway_app(make_gateway_settings())
    return TestClient(app)


def test_gateway_search_proxies_raw_payload_and_etag(client: TestClient) -> None:
    captured_headers: dict[str, str] = {}
    captured_body: dict = {}
    captured_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_headers.update(dict(request.headers))
        captured_urls.append(str(request.url))
        captured_body.update(json.loads(request.content.decode()))
        return httpx.Response(200, json={"response": {"docs": [{"lotNumberStr": "123"}], "numFound": 1}}, headers={"etag": '"search-etag"'})

    with client:
        client.app.state.gateway_service_factory = lambda: CopartGatewayService(
            settings=client.app.state.settings,
            client_factory=lambda: make_gateway_client(client.app.state.settings, handler),
        )
        response = client.post(
            "/v1/search",
            json={"MISC": ["lot_number:123"], "pageNumber": 1},
            headers={
                "Authorization": "Bearer gateway-secret",
                "If-None-Match": '"previous-search-etag"',
            },
        )

    assert response.status_code == 200
    assert response.headers["etag"] == '"search-etag"'
    assert response.json() == {"response": {"docs": [{"lotNumberStr": "123"}], "numFound": 1}}
    assert captured_urls == ["https://mmember.copart.com/srch/?services=bidIncrementsBySiteV2"]
    assert captured_headers["devicename"] == "iPhone 15 Pro Max"
    assert captured_headers["x-d-token"] == "token-123"
    assert captured_headers["cookie"] == "SessionID=abc"
    assert captured_headers["if-none-match"] == '"previous-search-etag"'
    assert captured_body == {"MISC": ["lot_number:123"], "pageNumber": 1}


def test_gateway_lot_details_preserves_304_not_modified_and_etag(client: TestClient) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(304, headers={"etag": '"lot-etag"'})

    with client:
        client.app.state.gateway_service_factory = lambda: CopartGatewayService(
            settings=client.app.state.settings,
            client_factory=lambda: make_gateway_client(client.app.state.settings, handler),
        )
        response = client.post(
            "/v1/lot-details",
            json={"lotNumber": 76880725},
            headers={
                "Authorization": "Bearer gateway-secret",
                "If-None-Match": '"previous-lot-etag"',
            },
        )

    assert response.status_code == 304
    assert response.headers["etag"] == '"lot-etag"'
    assert response.text == ""


def test_gateway_search_keywords_passthrough(client: TestClient) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ford": {"type": "MAKE_MODEL"}})

    with client:
        client.app.state.gateway_service_factory = lambda: CopartGatewayService(
            settings=client.app.state.settings,
            client_factory=lambda: make_gateway_client(client.app.state.settings, handler),
        )
        response = client.get(
            "/v1/search-keywords",
            headers={"Authorization": "Bearer gateway-secret"},
        )

    assert response.status_code == 200
    assert response.json() == {"ford": {"type": "MAKE_MODEL"}}


def test_gateway_search_count_endpoint_proxies_request(client: TestClient) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"response": {"numFound": 41}})

    with client:
        client.app.state.gateway_service_factory = lambda: CopartGatewayService(
            settings=client.app.state.settings,
            client_factory=lambda: make_gateway_client(client.app.state.settings, handler),
        )
        response = client.post(
            "/v1/search-count",
            json={"MISC": ["lot_make_code:FORD"]},
            headers={"Authorization": "Bearer gateway-secret"},
        )

    assert response.status_code == 200
    assert response.json() == {"response": {"numFound": 41}}


def test_gateway_router_logs_structured_proxy_events(client: TestClient, caplog) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"response": {"docs": [], "numFound": 0}}, headers={"etag": '"etag-1"'})

    with caplog.at_level(logging.INFO):
        with client:
            client.app.state.gateway_service_factory = lambda: CopartGatewayService(
                settings=client.app.state.settings,
                client_factory=lambda: make_gateway_client(client.app.state.settings, handler),
            )
            response = client.post(
                "/v1/search",
                json={"pageNumber": 1},
                headers={"Authorization": "Bearer gateway-secret"},
            )

    assert response.status_code == 200
    success_record = next(
        record for record in caplog.records if getattr(record, "event", "") == "copart_gateway.proxy.search.success"
    )
    assert success_record.structured["correlation_id"].startswith("gateway-proxy-")
    assert success_record.structured["has_etag"] is True


def test_gateway_rejects_invalid_or_missing_bearer_token(client: TestClient) -> None:
    with client:
        missing_token_response = client.post("/v1/search", json={"pageNumber": 1})
        invalid_token_response = client.post(
            "/v1/search",
            json={"pageNumber": 1},
            headers={"Authorization": "Bearer wrong-token"},
        )

    assert missing_token_response.status_code == 401
    assert invalid_token_response.status_code == 401


def test_gateway_maps_upstream_http_errors_to_explicit_headers(client: TestClient) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"error": "blocked"})

    with client:
        client.app.state.gateway_service_factory = lambda: CopartGatewayService(
            settings=client.app.state.settings,
            client_factory=lambda: make_gateway_client(client.app.state.settings, handler),
        )
        response = client.post(
            "/v1/search",
            json={"pageNumber": 1},
            headers={"Authorization": "Bearer gateway-secret"},
        )

    assert response.status_code == 502
    assert response.headers["x-copart-gateway-error"] == "upstream_rejected"
    assert response.headers["x-copart-upstream-status"] == "403"
    assert response.json()["detail"] == "Copart upstream request failed."


def test_gateway_maps_transport_failures_to_service_unavailable(client: TestClient) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("network down", request=request)

    with client:
        client.app.state.gateway_service_factory = lambda: CopartGatewayService(
            settings=client.app.state.settings,
            client_factory=lambda: make_gateway_client(client.app.state.settings, handler),
        )
        response = client.post(
            "/v1/search",
            json={"pageNumber": 1},
            headers={"Authorization": "Bearer gateway-secret"},
        )

    assert response.status_code == 503
    assert response.headers["x-copart-gateway-error"] == "unavailable"
    assert response.json()["detail"] == "Copart upstream is unavailable."


def test_gateway_maps_invalid_upstream_json_to_malformed_response_error(client: TestClient) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not-json")

    with client:
        client.app.state.gateway_service_factory = lambda: CopartGatewayService(
            settings=client.app.state.settings,
            client_factory=lambda: make_gateway_client(client.app.state.settings, handler),
        )
        response = client.post(
            "/v1/search",
            json={"pageNumber": 1},
            headers={"Authorization": "Bearer gateway-secret"},
        )

    assert response.status_code == 502
    assert response.headers["x-copart-gateway-error"] == "malformed_response"
    assert response.json()["detail"] == "Copart upstream returned malformed JSON."


def test_gateway_validates_request_payload_shape(client: TestClient) -> None:
    with client:
        response = client.post(
            "/v1/lot-details",
            json={},
            headers={"Authorization": "Bearer gateway-secret"},
        )

    assert response.status_code == 422


def test_gateway_returns_500_when_token_is_not_configured() -> None:
    client = TestClient(create_gateway_app(make_gateway_settings(COPART_GATEWAY_TOKEN=None)))

    with client:
        response = client.post(
            "/v1/search",
            json={"pageNumber": 1},
            headers={"Authorization": "Bearer gateway-secret"},
        )

    assert response.status_code == 500
    assert response.json()["detail"] == "Gateway bearer token is not configured."
