from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys

import mongomock
from fastapi.testclient import TestClient
import pytest


ROOT = Path(__file__).resolve().parents[2] / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


import cartrap.app as app_module
from cartrap.config import Settings
from cartrap.modules.iaai_provider.client import (
    IaaiConnectorBootstrapResult,
    IaaiEncryptedSessionBundle,
)
from cartrap.modules.iaai_provider.errors import IaaiAuthenticationError, IaaiDiagnostics, IaaiWafError


class FakeMongoManager:
    def __init__(self, uri: str, database_name: str, ping_on_startup: bool = False) -> None:
        self._database_name = database_name
        self._client = None

    def connect(self) -> None:
        self._client = mongomock.MongoClient(tz_aware=True)

    @property
    def database(self):
        return self._client[self._database_name]

    def close(self) -> None:
        self._client = None


class FakeIaaiConnectorClient:
    def bootstrap_connector_session(self, *, username: str, password: str, client_ip: str | None = None) -> IaaiConnectorBootstrapResult:
        del client_ip
        if password == "bad-password":
            raise IaaiAuthenticationError("bad credentials")
        if password == "blocked-password":
            raise IaaiWafError(
                "blocked",
                diagnostics=IaaiDiagnostics(
                    correlation_id="cid-iaai-test",
                    step="imperva_preflight",
                    error_code="upstream_rejected",
                    failure_class="upstream_rejected",
                    upstream_status_code=403,
                    hint="imperva_or_waf",
                ),
            )
        bundle = IaaiEncryptedSessionBundle(
            encrypted_bundle=f"iaai:{username}",
            key_version="v1",
            captured_at=datetime.now(timezone.utc),
            expires_at=datetime(2026, 12, 31, tzinfo=timezone.utc),
        )
        return IaaiConnectorBootstrapResult(
            bundle=bundle,
            account_label=username,
            connection_status="connected",
            verified_at=datetime.now(timezone.utc),
        )

    def close(self) -> None:
        return None


class FakeCopartConnectorClient:
    def bootstrap_connector_session(self, *, username: str, password: str, client_ip: str | None = None):
        del password
        del client_ip
        bundle = IaaiEncryptedSessionBundle(
            encrypted_bundle=f"copart:{username}",
            key_version="v1",
            captured_at=datetime.now(timezone.utc),
            expires_at=datetime(2026, 12, 31, tzinfo=timezone.utc),
        )
        return IaaiConnectorBootstrapResult(
            bundle=bundle,
            account_label=username,
            connection_status="connected",
            verified_at=datetime.now(timezone.utc),
        )

    def close(self) -> None:
        return None


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(app_module, "MongoManager", FakeMongoManager)
    settings = Settings(
        environment="test",
        mongo_uri="mongodb://unused",
        mongo_db="cartrap_test",
        jwt_secret="test-secret-123-test-secret-123x",
        jwt_refresh_secret="refresh-secret-123-refresh-secret-123",
        bootstrap_admin_email="admin@example.com",
        bootstrap_admin_password="AdminPass123",
    )
    app = app_module.create_app(settings)
    app.state.copart_connector_client_factory = FakeCopartConnectorClient
    app.state.iaai_connector_client_factory = FakeIaaiConnectorClient
    return TestClient(app)


def _login(client: TestClient, email: str, password: str) -> str:
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    return response.json()["access_token"]


def _create_user(client: TestClient, email: str, password: str) -> str:
    admin_token = _login(client, "admin@example.com", "AdminPass123")
    invite = client.post(
        "/api/admin/invites",
        json={"email": email},
        headers={"Authorization": f"Bearer {admin_token}"},
    ).json()
    client.post("/api/auth/invites/accept", json={"token": invite["token"], "password": password})
    return _login(client, email, password)


def test_iaai_router_connects_reconnects_and_disconnects(client: TestClient) -> None:
    with client as api:
        token = _create_user(api, "iaai@example.com", "OwnerPass123")
        headers = {"Authorization": f"Bearer {token}"}

        connect_response = api.post(
            "/api/provider-connections/iaai/connect",
            json={"username": "iaai@example.com", "password": "secret"},
            headers=headers,
        )
        reconnect_response = api.post(
            "/api/provider-connections/iaai/reconnect",
            json={"username": "iaai-2@example.com", "password": "secret"},
            headers=headers,
        )
        disconnect_response = api.delete("/api/provider-connections/iaai", headers=headers)

    assert connect_response.status_code == 200
    assert connect_response.json()["connection"]["provider"] == "iaai"
    assert reconnect_response.status_code == 200
    assert reconnect_response.json()["connection"]["account_label"] == "iaai-2@example.com"
    assert disconnect_response.status_code == 200
    assert disconnect_response.json()["connection"]["status"] == "disconnected"


def test_iaai_router_maps_auth_and_waf_errors(client: TestClient) -> None:
    with client as api:
        token = _create_user(api, "broken-iaai@example.com", "OwnerPass123")
        headers = {"Authorization": f"Bearer {token}"}

        bad = api.post(
            "/api/provider-connections/iaai/connect",
            json={"username": "bad@example.com", "password": "bad-password"},
            headers=headers,
        )
        blocked = api.post(
            "/api/provider-connections/iaai/connect",
            json={"username": "blocked@example.com", "password": "blocked-password"},
            headers=headers,
        )

    assert bad.status_code == 401
    assert bad.json()["detail"] == "IAAI credentials were rejected."
    assert blocked.status_code == 502
    assert blocked.json()["detail"] == "IAAI rejected connector bootstrap request. Bootstrap step: imperva_preflight."
    assert blocked.headers["x-iaai-correlation-id"] == "cid-iaai-test"
    assert blocked.headers["x-iaai-bootstrap-step"] == "imperva_preflight"


def test_iaai_router_returns_missing_connection_errors(client: TestClient) -> None:
    with client as api:
        token = _create_user(api, "missing-iaai@example.com", "OwnerPass123")
        headers = {"Authorization": f"Bearer {token}"}

        reconnect_response = api.post(
            "/api/provider-connections/iaai/reconnect",
            json={"username": "missing-iaai@example.com", "password": "secret"},
            headers=headers,
        )
        disconnect_response = api.delete("/api/provider-connections/iaai", headers=headers)

    assert reconnect_response.status_code == 404
    assert reconnect_response.json()["detail"] == "IAAI connection not found."
    assert disconnect_response.status_code == 404
    assert disconnect_response.json()["detail"] == "IAAI connection not found."


def test_iaai_router_keeps_copart_connection_isolated(client: TestClient) -> None:
    with client as api:
        token = _create_user(api, "multi@example.com", "OwnerPass123")
        headers = {"Authorization": f"Bearer {token}"}

        copart_connect = api.post(
            "/api/provider-connections/copart/connect",
            json={"username": "copart@example.com", "password": "secret"},
            headers=headers,
        )
        iaai_connect = api.post(
            "/api/provider-connections/iaai/connect",
            json={"username": "iaai@example.com", "password": "secret"},
            headers=headers,
        )
        iaai_disconnect = api.delete("/api/provider-connections/iaai", headers=headers)
        listed = api.get("/api/provider-connections", headers=headers)

    assert copart_connect.status_code == 200
    assert iaai_connect.status_code == 200
    assert iaai_disconnect.status_code == 200
    assert listed.status_code == 200
    providers = {item["provider"]: item["status"] for item in listed.json()["items"]}
    assert providers["copart"] == "connected"
    assert providers["iaai"] == "disconnected"
