from __future__ import annotations

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
    return TestClient(app)


def admin_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/auth/login",
        json={"email": "admin@example.com", "password": "AdminPass123"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_admin_can_create_and_revoke_invite(client: TestClient) -> None:
    with client:
        create_response = client.post(
            "/api/admin/invites",
            json={"email": "buyer@example.com"},
            headers=admin_headers(client),
        )

        assert create_response.status_code == 200
        invite = create_response.json()
        assert invite["email"] == "buyer@example.com"
        assert invite["status"] == "pending"

        revoke_response = client.delete(
            f"/api/admin/invites/{invite['id']}",
            headers=admin_headers(client),
        )

    assert revoke_response.status_code == 200
    assert revoke_response.json()["status"] == "revoked"


def test_accept_invite_creates_user(client: TestClient) -> None:
    with client:
        invite = client.post(
            "/api/admin/invites",
            json={"email": "driver@example.com"},
            headers=admin_headers(client),
        ).json()

        response = client.post(
            "/api/auth/invites/accept",
            json={"token": invite["token"], "password": "DriverPass123"},
        )

    assert response.status_code == 201
    assert response.json()["user"]["email"] == "driver@example.com"
    assert response.json()["user"]["role"] == "user"


def test_accept_rejected_for_unknown_invite(client: TestClient) -> None:
    with client:
        response = client.post(
            "/api/auth/invites/accept",
            json={"token": "missing-token-value", "password": "DriverPass123"},
        )

    assert response.status_code == 404
