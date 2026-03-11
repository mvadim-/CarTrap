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


def test_login_and_refresh_flow(client: TestClient) -> None:
    with client:
        login_response = client.post(
            "/api/auth/login",
            json={"email": "admin@example.com", "password": "AdminPass123"},
        )
        assert login_response.status_code == 200

        refresh_response = client.post(
            "/api/auth/refresh",
            json={"refresh_token": login_response.json()["refresh_token"]},
        )

    assert refresh_response.status_code == 200
    assert refresh_response.json()["token_type"] == "bearer"
    assert refresh_response.json()["access_token"]


def test_login_rejects_invalid_password(client: TestClient) -> None:
    with client:
        response = client.post(
            "/api/auth/login",
            json={"email": "admin@example.com", "password": "WrongPass123"},
        )

    assert response.status_code == 401
