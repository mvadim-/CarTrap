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


def test_admin_route_requires_token(client: TestClient) -> None:
    with client:
        response = client.post("/api/admin/invites", json={"email": "buyer@example.com"})

    assert response.status_code == 401


def test_admin_route_rejects_regular_user(client: TestClient) -> None:
    with client:
        admin_token = client.post(
            "/api/auth/login",
            json={"email": "admin@example.com", "password": "AdminPass123"},
        ).json()["access_token"]

        invite = client.post(
            "/api/admin/invites",
            json={"email": "member@example.com"},
            headers={"Authorization": f"Bearer {admin_token}"},
        ).json()

        client.post(
            "/api/auth/invites/accept",
            json={"token": invite["token"], "password": "MemberPass123"},
        )

        user_token = client.post(
            "/api/auth/login",
            json={"email": "member@example.com", "password": "MemberPass123"},
        ).json()["access_token"]

        response = client.post(
            "/api/admin/invites",
            json={"email": "blocked@example.com"},
            headers={"Authorization": f"Bearer {user_token}"},
        )

    assert response.status_code == 403


def test_admin_route_rejects_blocked_admin_with_existing_token(client: TestClient) -> None:
    with client:
        admin_token = client.post(
            "/api/auth/login",
            json={"email": "admin@example.com", "password": "AdminPass123"},
        ).json()["access_token"]
        client.app.state.mongo.database["users"].update_one(
            {"email": "admin@example.com"},
            {"$set": {"status": "blocked"}},
        )

        response = client.post(
            "/api/admin/invites",
            json={"email": "buyer@example.com"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    assert response.status_code == 401
    assert response.json()["detail"] == "User account is blocked."
