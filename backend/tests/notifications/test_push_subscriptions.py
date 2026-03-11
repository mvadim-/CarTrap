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
    return TestClient(app_module.create_app(settings))


def _login(client: TestClient, email: str, password: str) -> str:
    return client.post("/api/auth/login", json={"email": email, "password": password}).json()["access_token"]


def _create_user(client: TestClient, email: str, password: str) -> str:
    admin_token = _login(client, "admin@example.com", "AdminPass123")
    invite = client.post(
        "/api/admin/invites",
        json={"email": email},
        headers={"Authorization": f"Bearer {admin_token}"},
    ).json()
    client.post("/api/auth/invites/accept", json={"token": invite["token"], "password": password})
    return _login(client, email, password)


def test_subscription_crud_flow(client: TestClient) -> None:
    with client:
        user_token = _create_user(client, "push@example.com", "PushPass123")
        headers = {"Authorization": f"Bearer {user_token}"}
        payload = {
            "subscription": {
                "endpoint": "https://push.example.test/subscriptions/1",
                "expirationTime": None,
                "keys": {"p256dh": "abc", "auth": "def"},
            },
            "user_agent": "Firefox",
        }

        create_response = client.post("/api/notifications/subscriptions", json=payload, headers=headers)
        assert create_response.status_code == 201

        list_response = client.get("/api/notifications/subscriptions", headers=headers)
        assert list_response.status_code == 200
        assert len(list_response.json()["items"]) == 1

        delete_response = client.delete(
            "/api/notifications/subscriptions",
            params={"endpoint": "https://push.example.test/subscriptions/1"},
            headers=headers,
        )

        assert delete_response.status_code == 204
        assert client.get("/api/notifications/subscriptions", headers=headers).json()["items"] == []


def test_unsubscribe_unknown_endpoint_returns_404(client: TestClient) -> None:
    with client:
        user_token = _create_user(client, "push404@example.com", "PushPass123")
        response = client.delete(
            "/api/notifications/subscriptions",
            params={"endpoint": "https://push.example.test/subscriptions/missing"},
            headers={"Authorization": f"Bearer {user_token}"},
        )

    assert response.status_code == 404
