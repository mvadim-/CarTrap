from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys

from fastapi.testclient import TestClient
import pytest


ROOT = Path(__file__).resolve().parents[2] / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from cartrap.config import Settings
from cartrap.gateway_app import create_gateway_app
from cartrap.modules.copart_gateway.service import CopartGatewayService
from cartrap.modules.copart_provider.client import (
    CopartConnectorBootstrapResult,
    CopartConnectorExecutionResult,
    CopartSessionBundle,
    CopartHeaderProfile,
)
from cartrap.modules.copart_provider.errors import CopartAuthenticationError, CopartSessionInvalidError


class FakeDirectConnectorClient:
    def bootstrap_connector_session(self, *, username: str, password: str) -> CopartConnectorBootstrapResult:
        if password == "bad":
            raise CopartAuthenticationError("bad credentials")
        return CopartConnectorBootstrapResult(
            bundle=_make_raw_bundle(),
            account_label=username,
            connection_status="connected",
            verified_at=datetime(2026, 3, 24, 17, 0, tzinfo=timezone.utc),
        )

    def verify_connector_session(self, bundle):
        return CopartConnectorExecutionResult(
            payload={"me": {"email": "user@example.com"}},
            bundle=bundle,
            etag=None,
            not_modified=False,
            connection_status="connected",
            verified_at=datetime(2026, 3, 24, 17, 1, tzinfo=timezone.utc),
            used_at=datetime(2026, 3, 24, 17, 1, tzinfo=timezone.utc),
        )

    def search_with_connector_session(self, payload, bundle):
        return CopartConnectorExecutionResult(
            payload={"response": {"docs": [{"lot_number": "12345678"}], "numFound": 1}},
            bundle=bundle,
            etag='"search-etag"',
            not_modified=False,
            connection_status="connected",
            verified_at=datetime(2026, 3, 24, 17, 2, tzinfo=timezone.utc),
            used_at=datetime(2026, 3, 24, 17, 2, tzinfo=timezone.utc),
        )

    def lot_details_with_connector_session(self, lot_number, bundle, etag=None):
        del etag
        if lot_number == "99999999":
            raise CopartSessionInvalidError("expired")
        return CopartConnectorExecutionResult(
            payload={"lotDetails": {"lotNumber": int(lot_number)}},
            bundle=bundle,
            etag='"lot-etag"',
            not_modified=False,
            connection_status="connected",
            verified_at=datetime(2026, 3, 24, 17, 3, tzinfo=timezone.utc),
            used_at=datetime(2026, 3, 24, 17, 3, tzinfo=timezone.utc),
        )

    def close(self) -> None:
        return None


def _make_raw_bundle() -> CopartSessionBundle:
    return CopartSessionBundle(
        session_id="session-1",
        d_token="token-1",
        device_id="device-1",
        ins_sess="ins-1",
        cookies=(("SessionID", "session-1"), ("incap_ses_1", "cookie-1")),
        header_profile=CopartHeaderProfile(
            device_name="iPhone 15 Pro Max",
            site_code="CPRTUS",
            company="Copart",
            os="iOS",
            language_code="en",
            client_app_version="6.2.1",
            user_agent="CopartTestAgent",
        ),
        expires_at=datetime(2026, 12, 31, tzinfo=timezone.utc),
        captured_at=datetime(2026, 3, 24, 17, 0, tzinfo=timezone.utc),
    )


@pytest.fixture
def client() -> TestClient:
    settings = Settings(
        ENVIRONMENT="test",
        APP_NAME="CarTrap Gateway Test",
        MONGO_URI="mongodb://unused",
        MONGO_DB="cartrap_test",
        COPART_GATEWAY_BASE_URL=None,
        COPART_GATEWAY_TOKEN="gateway-secret",
        COPART_CONNECTOR_ENCRYPTION_KEY="m2xwGL3J9f-hDyiI2FQpJjzC9Y0mbmN81fUSWbTtPqk=",
    )
    app = create_gateway_app(settings)
    return TestClient(app)


def test_gateway_connector_bootstrap_and_execute_flow_round_trips_encrypted_bundle(client: TestClient) -> None:
    with client:
        client.app.state.gateway_service_factory = lambda: CopartGatewayService(
            settings=client.app.state.settings,
            client_factory=FakeDirectConnectorClient,
        )
        bootstrap_response = client.post(
            "/v1/connector/bootstrap",
            json={"username": "user@example.com", "password": "secret"},
            headers={"Authorization": "Bearer gateway-secret"},
        )
        encrypted_bundle = bootstrap_response.json()["session_bundle"]
        verify_response = client.post(
            "/v1/connector/verify",
            json={"session_bundle": encrypted_bundle},
            headers={"Authorization": "Bearer gateway-secret"},
        )
        search_response = client.post(
            "/v1/connector/execute/search",
            json={"session_bundle": encrypted_bundle, "search_payload": {"pageNumber": 1}},
            headers={"Authorization": "Bearer gateway-secret"},
        )
        lot_response = client.post(
            "/v1/connector/execute/lot-details",
            json={"session_bundle": encrypted_bundle, "lot_number": 12345678},
            headers={"Authorization": "Bearer gateway-secret"},
        )

    assert bootstrap_response.status_code == 200
    assert bootstrap_response.json()["status"] == "connected"
    assert bootstrap_response.json()["session_bundle"]["encrypted_bundle"]
    assert verify_response.status_code == 200
    assert verify_response.json()["payload"] == {"me": {"email": "user@example.com"}}
    assert search_response.status_code == 200
    assert search_response.json()["payload"]["response"]["numFound"] == 1
    assert lot_response.status_code == 200
    assert lot_response.json()["payload"]["lotDetails"]["lotNumber"] == 12345678


def test_gateway_connector_maps_auth_invalid_and_invalid_credentials(client: TestClient) -> None:
    with client:
        client.app.state.gateway_service_factory = lambda: CopartGatewayService(
            settings=client.app.state.settings,
            client_factory=FakeDirectConnectorClient,
        )
        invalid_credentials = client.post(
            "/v1/connector/bootstrap",
            json={"username": "user@example.com", "password": "bad"},
            headers={"Authorization": "Bearer gateway-secret"},
        )
        bootstrap_response = client.post(
            "/v1/connector/bootstrap",
            json={"username": "user@example.com", "password": "secret"},
            headers={"Authorization": "Bearer gateway-secret"},
        )
        auth_invalid = client.post(
            "/v1/connector/execute/lot-details",
            json={"session_bundle": bootstrap_response.json()["session_bundle"], "lot_number": 99999999},
            headers={"Authorization": "Bearer gateway-secret"},
        )

    assert invalid_credentials.status_code == 401
    assert invalid_credentials.headers["x-copart-gateway-error"] == "invalid_credentials"
    assert auth_invalid.status_code == 409
    assert auth_invalid.headers["x-copart-gateway-error"] == "auth_invalid"


def test_gateway_connector_reports_invalid_encryption_key_configuration() -> None:
    settings = Settings(
        ENVIRONMENT="test",
        APP_NAME="CarTrap Gateway Test",
        MONGO_URI="mongodb://unused",
        MONGO_DB="cartrap_test",
        COPART_GATEWAY_BASE_URL=None,
        COPART_GATEWAY_TOKEN="gateway-secret",
        COPART_CONNECTOR_ENCRYPTION_KEY="not-a-valid-fernet-key",
    )
    app = create_gateway_app(settings)
    client = TestClient(app)

    with client:
        client.app.state.gateway_service_factory = lambda: CopartGatewayService(
            settings=client.app.state.settings,
            client_factory=FakeDirectConnectorClient,
        )
        response = client.post(
            "/v1/connector/bootstrap",
            json={"username": "user@example.com", "password": "secret"},
            headers={"Authorization": "Bearer gateway-secret"},
        )

    assert response.status_code == 500
    assert response.json()["detail"] == "COPART_CONNECTOR_ENCRYPTION_KEY is invalid."
