from pathlib import Path
import sys

import httpx
from fastapi.testclient import TestClient
import pytest


ROOT = Path(__file__).resolve().parents[2] / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from cartrap.config import Settings
from cartrap.iaai_gateway_app import create_iaai_gateway_app
from cartrap.modules.iaai_gateway.service import IaaiGatewayService
from cartrap.modules.iaai_provider.client import IaaiHttpClient


def make_gateway_settings(**overrides: object) -> Settings:
    payload = {
        "ENVIRONMENT": "test",
        "APP_NAME": "CarTrap IAAI Gateway Test",
        "MONGO_URI": "mongodb://unused",
        "MONGO_DB": "cartrap_test",
        "IAAI_GATEWAY_BASE_URL": None,
        "IAAI_GATEWAY_TOKEN": "gateway-secret",
        "IAAI_CONNECTOR_ENCRYPTION_KEY": "m2xwGL3J9f-hDyiI2FQpJjzC9Y0mbmN81fUSWbTtPqk=",
        "IAAI_MOBILE_SEARCH_PATH": "https://api.test/search",
        "IAAI_MOBILE_INVENTORY_DETAILS_PATH": "https://api.test/inventory/{provider_lot_id}",
    }
    payload.update(overrides)
    return Settings(**payload)


def make_gateway_client(settings: Settings, handler) -> IaaiHttpClient:
    return IaaiHttpClient(
        settings=settings.model_copy(update={"iaai_gateway_base_url": None}),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


@pytest.fixture
def client() -> TestClient:
    app = create_iaai_gateway_app(make_gateway_settings())
    return TestClient(app)


def test_gateway_search_proxies_raw_payload_and_etag(client: TestClient) -> None:
    captured_urls: list[str] = []
    captured_headers: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_urls.append(str(request.url))
        captured_headers.update(dict(request.headers))
        return httpx.Response(200, json={"vehicles": [], "totalCount": 0}, headers={"etag": '"search-etag"'})

    with client:
        client.app.state.gateway_service_factory = lambda: IaaiGatewayService(
            settings=client.app.state.settings,
            client_factory=lambda: make_gateway_client(client.app.state.settings, handler),
        )
        response = client.post(
            "/v1/search",
            json={"keyword": "mustang"},
            headers={"Authorization": "Bearer gateway-secret", "If-None-Match": '"old-etag"'},
        )

    assert response.status_code == 200
    assert response.headers["etag"] == '"search-etag"'
    assert response.json() == {"vehicles": [], "totalCount": 0}
    assert captured_urls == ["https://api.test/search"]
    assert captured_headers["if-none-match"] == '"old-etag"'


def test_gateway_lot_details_preserves_304(client: TestClient) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(304, headers={"etag": '"lot-etag"'})

    with client:
        client.app.state.gateway_service_factory = lambda: IaaiGatewayService(
            settings=client.app.state.settings,
            client_factory=lambda: make_gateway_client(client.app.state.settings, handler),
        )
        response = client.post(
            "/v1/lot-details",
            json={"provider_lot_id": "99112233"},
            headers={"Authorization": "Bearer gateway-secret", "If-None-Match": '"old-lot-etag"'},
        )

    assert response.status_code == 304
    assert response.headers["etag"] == '"lot-etag"'


def test_gateway_rejects_invalid_or_missing_bearer_token(client: TestClient) -> None:
    with client:
        missing = client.post("/v1/search", json={"keyword": "mustang"})
        invalid = client.post(
            "/v1/search",
            json={"keyword": "mustang"},
            headers={"Authorization": "Bearer wrong-token"},
        )

    assert missing.status_code == 401
    assert invalid.status_code == 401
