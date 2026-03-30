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
from cartrap.modules.notifications.service import build_subscription_config, build_web_push_sender


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


class FakeSender:
    def __init__(self) -> None:
        self.sent: list[tuple[str, dict]] = []

    def send(self, subscription: dict, payload: dict) -> None:
        self.sent.append((subscription["endpoint"], payload))


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(app_module, "MongoManager", FakeMongoManager)
    settings = Settings(
        _env_file=None,
        environment="test",
        mongo_uri="mongodb://unused",
        mongo_db="cartrap_test",
        jwt_secret="test-secret-123-test-secret-123x",
        jwt_refresh_secret="refresh-secret-123-refresh-secret-123",
        bootstrap_admin_email="admin@example.com",
        bootstrap_admin_password="AdminPass123",
    )
    return TestClient(app_module.create_app(settings))


@pytest.fixture
def client_with_vapid(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(app_module, "MongoManager", FakeMongoManager)
    settings = Settings(
        _env_file=None,
        environment="test",
        mongo_uri="mongodb://unused",
        mongo_db="cartrap_test",
        jwt_secret="test-secret-123-test-secret-123x",
        jwt_refresh_secret="refresh-secret-123-refresh-secret-123",
        bootstrap_admin_email="admin@example.com",
        bootstrap_admin_password="AdminPass123",
        vapid_public_key="BEl62iUYgUivTB1X4VQx-FakePublicKey1234567890",
        vapid_private_key="ZL6eK1-fake-private-key-1234567890",
        vapid_subject="mailto:admin@example.com",
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


def test_subscription_config_reports_disabled_without_vapid_key(client: TestClient) -> None:
    with client:
        user_token = _create_user(client, "push-config-off@example.com", "PushPass123")
        response = client.get(
            "/api/notifications/subscription-config",
            headers={"Authorization": f"Bearer {user_token}"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "enabled": False,
        "public_key": None,
        "reason": "Push notifications are not configured on the server. Missing: VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY, VAPID_SUBJECT.",
    }


def test_subscription_config_returns_public_key_when_enabled(client_with_vapid: TestClient) -> None:
    with client_with_vapid:
        user_token = _create_user(client_with_vapid, "push-config-on@example.com", "PushPass123")
        response = client_with_vapid.get(
            "/api/notifications/subscription-config",
            headers={"Authorization": f"Bearer {user_token}"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "enabled": True,
        "public_key": "BEl62iUYgUivTB1X4VQx-FakePublicKey1234567890",
        "reason": None,
    }


def test_subscription_config_reports_disabled_when_vapid_private_key_path_is_missing(tmp_path: Path) -> None:
    missing_key_path = tmp_path / "missing_private_key.pem"

    config = build_subscription_config(
        vapid_public_key="public-key",
        vapid_private_key=str(missing_key_path),
        vapid_subject="mailto:admin@example.com",
    )

    assert config == {
        "enabled": False,
        "public_key": None,
        "reason": f"Push notifications are not configured on the server. VAPID private key file is missing: {missing_key_path}.",
    }


def test_build_web_push_sender_returns_none_when_vapid_private_key_path_is_missing(tmp_path: Path) -> None:
    missing_key_path = tmp_path / "missing_private_key.pem"

    sender = build_web_push_sender(
        vapid_private_key=str(missing_key_path),
        vapid_subject="mailto:admin@example.com",
    )

    assert sender is None


def test_send_test_push_delivers_to_current_user_subscriptions(
    client_with_vapid: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sender = FakeSender()
    monkeypatch.setattr(app_module, "build_web_push_sender", lambda vapid_private_key, vapid_subject: sender)

    with client_with_vapid:
        user_token = _create_user(client_with_vapid, "push-test@example.com", "PushPass123")
        headers = {"Authorization": f"Bearer {user_token}"}
        create_payload = {
            "subscription": {
                "endpoint": "https://push.example.test/subscriptions/test-device",
                "expirationTime": None,
                "keys": {"p256dh": "abc", "auth": "def"},
            },
            "user_agent": "Firefox",
        }
        create_response = client_with_vapid.post("/api/notifications/subscriptions", json=create_payload, headers=headers)
        assert create_response.status_code == 201

        response = client_with_vapid.post(
            "/api/notifications/test",
            json={"title": "Manual push check", "body": "Browser push path is alive."},
            headers=headers,
        )

    assert response.status_code == 200
    assert response.json() == {
        "delivered": 1,
        "failed": 0,
        "removed": 0,
        "endpoints": ["https://push.example.test/subscriptions/test-device"],
    }
    assert sender.sent == [
        (
            "https://push.example.test/subscriptions/test-device",
            {
                "title": "Manual push check",
                "body": "Browser push path is alive.",
                "test": True,
                "notification_type": "test",
                "refresh_targets": [],
            },
        )
    ]
