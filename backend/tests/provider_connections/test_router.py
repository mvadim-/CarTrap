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
from cartrap.modules.copart_provider.client import (
    CopartConnectorBootstrapResult,
    CopartConnectorExecutionResult,
    CopartEncryptedSessionBundle,
)
from cartrap.modules.copart_provider.errors import CopartAuthenticationError
from cartrap.modules.copart_provider.errors import CopartChallengeError
from cartrap.modules.copart_provider.errors import CopartGatewayUpstreamError


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


class FakeConnectorClient:
    def bootstrap_connector_session(self, *, username: str, password: str) -> CopartConnectorBootstrapResult:
        if password == "bad-password":
            raise CopartAuthenticationError("bad credentials")
        if password == "challenge-password":
            raise CopartChallengeError("challenge failed")
        if password == "blocked-password":
            raise CopartGatewayUpstreamError("blocked", upstream_status_code=403)
        bundle = CopartEncryptedSessionBundle(
            encrypted_bundle=f"bundle:{username}",
            key_version="v1",
            captured_at=datetime.now(timezone.utc),
            expires_at=datetime(2026, 12, 31, tzinfo=timezone.utc),
        )
        return CopartConnectorBootstrapResult(
            bundle=bundle,
            account_label=username,
            connection_status="connected",
            verified_at=datetime.now(timezone.utc),
        )

    def search_with_connector_session(self, payload, bundle):
        del payload
        del bundle
        return CopartConnectorExecutionResult(
            payload={"response": {"docs": [], "numFound": 0}},
            bundle=None,
            etag=None,
            not_modified=False,
            connection_status="connected",
            verified_at=datetime.now(timezone.utc),
            used_at=datetime.now(timezone.utc),
        )

    def lot_details_with_connector_session(self, lot_number, bundle, etag=None):
        del lot_number
        del bundle
        del etag
        return CopartConnectorExecutionResult(
            payload={"lotDetails": {"lotNumber": 1}},
            bundle=None,
            etag=None,
            not_modified=False,
            connection_status="connected",
            verified_at=datetime.now(timezone.utc),
            used_at=datetime.now(timezone.utc),
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
    app.state.copart_connector_client_factory = FakeConnectorClient
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


def test_provider_connection_router_lists_connects_reconnects_and_disconnects(client: TestClient) -> None:
    with client:
        token = _create_user(client, "owner@example.com", "OwnerPass123")
        headers = {"Authorization": f"Bearer {token}"}

        initial_list = client.get("/api/provider-connections", headers=headers)
        connect_response = client.post(
            "/api/provider-connections/copart/connect",
            json={"username": "first@example.com", "password": "secret"},
            headers=headers,
        )
        reconnect_response = client.post(
            "/api/provider-connections/copart/reconnect",
            json={"username": "second@example.com", "password": "secret"},
            headers=headers,
        )
        final_list = client.get("/api/provider-connections", headers=headers)
        disconnect_response = client.delete("/api/provider-connections/copart", headers=headers)

    assert initial_list.status_code == 200
    assert initial_list.json()["items"] == []
    assert connect_response.status_code == 200
    assert connect_response.json()["connection"]["account_label"] == "first@example.com"
    assert reconnect_response.status_code == 200
    assert reconnect_response.json()["connection"]["account_label"] == "second@example.com"
    assert final_list.status_code == 200
    assert len(final_list.json()["items"]) == 1
    assert final_list.json()["items"][0]["account_label"] == "second@example.com"
    assert disconnect_response.status_code == 200
    assert disconnect_response.json()["connection"]["status"] == "disconnected"


def test_provider_connection_router_maps_invalid_credentials_and_missing_connection(client: TestClient) -> None:
    with client:
        token = _create_user(client, "bad@example.com", "BadPass123")
        headers = {"Authorization": f"Bearer {token}"}

        connect_response = client.post(
            "/api/provider-connections/copart/connect",
            json={"username": "bad@example.com", "password": "bad-password"},
            headers=headers,
        )
        reconnect_response = client.post(
            "/api/provider-connections/copart/reconnect",
            json={"username": "bad@example.com", "password": "secret"},
            headers=headers,
        )

    assert connect_response.status_code == 401
    assert connect_response.json()["detail"] == "Copart credentials were rejected."
    assert reconnect_response.status_code == 404


def test_provider_connection_router_maps_challenge_failures_to_bad_gateway(client: TestClient) -> None:
    with client:
        token = _create_user(client, "challenge@example.com", "ChallengePass123")
        headers = {"Authorization": f"Bearer {token}"}

        connect_response = client.post(
            "/api/provider-connections/copart/connect",
            json={"username": "challenge@example.com", "password": "challenge-password"},
            headers=headers,
        )

    assert connect_response.status_code == 502
    assert connect_response.json()["detail"] == "Copart connector bootstrap failed during upstream challenge replay."


def test_provider_connection_router_maps_upstream_rejection_to_bad_gateway(client: TestClient) -> None:
    with client:
        token = _create_user(client, "blocked@example.com", "BlockedPass123")
        headers = {"Authorization": f"Bearer {token}"}

        connect_response = client.post(
            "/api/provider-connections/copart/connect",
            json={"username": "blocked@example.com", "password": "blocked-password"},
            headers=headers,
        )

    assert connect_response.status_code == 502
    assert connect_response.json()["detail"] == "Copart rejected connector bootstrap request."
