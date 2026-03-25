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
from cartrap.iaai_gateway_app import create_iaai_gateway_app
from cartrap.modules.iaai_gateway.service import IaaiGatewayService
from cartrap.modules.iaai_provider.client import (
    IaaiConnectorBootstrapResult,
    IaaiConnectorExecutionResult,
    IaaiHeaderProfile,
    IaaiSessionBundle,
)
from cartrap.modules.iaai_provider.errors import IaaiAuthenticationError, IaaiDiagnostics, IaaiSessionInvalidError, IaaiWafError


class FakeDirectConnectorClient:
    last_correlation_id: str | None = None

    def bootstrap_connector_session(
        self,
        *,
        username: str,
        password: str,
        client_ip: str | None = None,
        correlation_id: str | None = None,
    ) -> IaaiConnectorBootstrapResult:
        del client_ip
        type(self).last_correlation_id = correlation_id
        if password == "bad":
            raise IaaiAuthenticationError("bad credentials")
        if password == "blocked":
            raise IaaiWafError(
                "blocked",
                diagnostics=IaaiDiagnostics(
                    correlation_id=correlation_id,
                    step="imperva_preflight",
                    error_code="upstream_rejected",
                    failure_class="upstream_rejected",
                    upstream_status_code=403,
                    hint="imperva_or_waf",
                ),
            )
        return IaaiConnectorBootstrapResult(
            bundle=_make_raw_bundle(username=username),
            account_label=username,
            connection_status="connected",
            verified_at=datetime(2026, 3, 25, 17, 0, tzinfo=timezone.utc),
        )

    def verify_connector_session(self, bundle):
        return IaaiConnectorExecutionResult(
            payload={"profile": {"email": bundle.account_label}},
            bundle=bundle,
            etag=None,
            not_modified=False,
            connection_status="connected",
            verified_at=datetime(2026, 3, 25, 17, 1, tzinfo=timezone.utc),
            used_at=datetime(2026, 3, 25, 17, 1, tzinfo=timezone.utc),
        )

    def search_with_connector_session(self, payload, bundle):
        del payload
        return IaaiConnectorExecutionResult(
            payload={"vehicles": [{"id": "99112233"}], "totalCount": 1},
            bundle=bundle,
            etag='"search-etag"',
            not_modified=False,
            connection_status="connected",
            verified_at=datetime(2026, 3, 25, 17, 2, tzinfo=timezone.utc),
            used_at=datetime(2026, 3, 25, 17, 2, tzinfo=timezone.utc),
        )

    def lot_details_with_connector_session(self, provider_lot_id, bundle, etag=None):
        del etag
        if provider_lot_id == "expired-lot":
            raise IaaiSessionInvalidError("expired")
        return IaaiConnectorExecutionResult(
            payload={"inventoryResult": {"inventoryId": provider_lot_id}},
            bundle=bundle,
            etag='"lot-etag"',
            not_modified=False,
            connection_status="connected",
            verified_at=datetime(2026, 3, 25, 17, 3, tzinfo=timezone.utc),
            used_at=datetime(2026, 3, 25, 17, 3, tzinfo=timezone.utc),
        )

    def close(self) -> None:
        return None


def _make_raw_bundle(*, username: str) -> IaaiSessionBundle:
    return IaaiSessionBundle(
        access_token="token-1",
        refresh_token="refresh-1",
        expires_at=datetime(2026, 12, 31, tzinfo=timezone.utc),
        account_label=username,
        user_id="user-1",
        cookies=(("reese84", "cookie-1"),),
        header_profile=IaaiHeaderProfile(
            tenant="US",
            apikey="mobile-app",
            deviceid="device-1",
            request_type="mobile",
            app_version="1.0.0",
            country="US",
            language="en-US",
            user_agent="IAA Buyer/1 CFNetwork/3860.500.112 Darwin/25.4.0",
        ),
        captured_at=datetime(2026, 3, 25, 17, 0, tzinfo=timezone.utc),
    )


@pytest.fixture
def client() -> TestClient:
    settings = Settings(
        ENVIRONMENT="test",
        APP_NAME="CarTrap IAAI Gateway Test",
        MONGO_URI="mongodb://unused",
        MONGO_DB="cartrap_test",
        IAAI_GATEWAY_BASE_URL=None,
        IAAI_GATEWAY_TOKEN="gateway-secret",
        IAAI_CONNECTOR_ENCRYPTION_KEY="m2xwGL3J9f-hDyiI2FQpJjzC9Y0mbmN81fUSWbTtPqk=",
    )
    app = create_iaai_gateway_app(settings)
    return TestClient(app)


def test_gateway_connector_bootstrap_and_execute_flow_round_trips_encrypted_bundle(client: TestClient) -> None:
    FakeDirectConnectorClient.last_correlation_id = None
    with client:
        client.app.state.gateway_service_factory = lambda: IaaiGatewayService(
            settings=client.app.state.settings,
            client_factory=FakeDirectConnectorClient,
        )
        bootstrap = client.post(
            "/v1/connector/bootstrap",
            json={"username": "user@example.com", "password": "secret"},
            headers={"Authorization": "Bearer gateway-secret", "X-Correlation-Id": "cid-123"},
        )
        encrypted_bundle = bootstrap.json()["session_bundle"]
        verify = client.post(
            "/v1/connector/verify",
            json={"session_bundle": encrypted_bundle},
            headers={"Authorization": "Bearer gateway-secret"},
        )
        search = client.post(
            "/v1/connector/execute/search",
            json={"session_bundle": encrypted_bundle, "search_payload": {"keyword": "mustang"}},
            headers={"Authorization": "Bearer gateway-secret"},
        )
        lot = client.post(
            "/v1/connector/execute/lot-details",
            json={"session_bundle": encrypted_bundle, "provider_lot_id": "99112233"},
            headers={"Authorization": "Bearer gateway-secret"},
        )

    assert bootstrap.status_code == 200
    assert bootstrap.json()["session_bundle"]["encrypted_bundle"]
    assert FakeDirectConnectorClient.last_correlation_id == "cid-123"
    assert verify.status_code == 200
    assert verify.json()["payload"] == {"profile": {"email": "user@example.com"}}
    assert search.status_code == 200
    assert search.json()["payload"]["totalCount"] == 1
    assert lot.status_code == 200
    assert lot.json()["payload"]["inventoryResult"]["inventoryId"] == "99112233"


def test_gateway_connector_maps_invalid_credentials_and_auth_invalid(client: TestClient) -> None:
    with client:
        client.app.state.gateway_service_factory = lambda: IaaiGatewayService(
            settings=client.app.state.settings,
            client_factory=FakeDirectConnectorClient,
        )
        invalid_credentials = client.post(
            "/v1/connector/bootstrap",
            json={"username": "user@example.com", "password": "bad"},
            headers={"Authorization": "Bearer gateway-secret"},
        )
        bootstrap = client.post(
            "/v1/connector/bootstrap",
            json={"username": "user@example.com", "password": "secret"},
            headers={"Authorization": "Bearer gateway-secret"},
        )
        auth_invalid = client.post(
            "/v1/connector/execute/lot-details",
            json={"session_bundle": bootstrap.json()["session_bundle"], "provider_lot_id": "expired-lot"},
            headers={"Authorization": "Bearer gateway-secret"},
        )

    assert invalid_credentials.status_code == 401
    assert invalid_credentials.headers["x-iaai-gateway-error"] == "invalid_credentials"
    assert invalid_credentials.json()["detail"] == "IAAI credentials were rejected."
    assert auth_invalid.status_code == 409
    assert auth_invalid.headers["x-iaai-gateway-error"] == "auth_invalid"


def test_gateway_connector_maps_waf_to_upstream_rejected(client: TestClient) -> None:
    with client:
        client.app.state.gateway_service_factory = lambda: IaaiGatewayService(
            settings=client.app.state.settings,
            client_factory=FakeDirectConnectorClient,
        )
        blocked = client.post(
            "/v1/connector/bootstrap",
            json={"username": "user@example.com", "password": "blocked"},
            headers={"Authorization": "Bearer gateway-secret"},
        )

    assert blocked.status_code == 502
    assert blocked.headers["x-iaai-gateway-error"] == "upstream_rejected"
    assert blocked.headers["x-iaai-upstream-status"] == "403"
    assert blocked.headers["x-iaai-bootstrap-step"] == "imperva_preflight"
    assert blocked.headers["x-iaai-failure-class"] == "upstream_rejected"
    assert blocked.json()["diagnostics"]["step"] == "imperva_preflight"
    assert blocked.json()["detail"] == "IAAI rejected connector bootstrap request."
