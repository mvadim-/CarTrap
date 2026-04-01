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
from cartrap.modules.auth.models import ROLE_USER, USER_STATUS_ACTIVE
from cartrap.modules.auth.service import AuthService


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


@pytest.fixture
def admin_headers(client: TestClient):
    def _admin_headers() -> dict[str, str]:
        response = client.post(
            "/api/auth/login",
            json={"email": "admin@example.com", "password": "AdminPass123"},
        )
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    return _admin_headers


@pytest.fixture
def create_user(client: TestClient):
    def _create_user(
        *,
        email: str,
        password: str = "UserPass123",
        role: str = ROLE_USER,
        status: str = USER_STATUS_ACTIVE,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
        last_login_at: datetime | None = None,
    ) -> str:
        now = created_at or datetime.now(timezone.utc)
        database = client.app.state.mongo.database
        result = database["users"].insert_one(
            {
                "email": email.lower(),
                "password_hash": AuthService.hash_password(password),
                "role": role,
                "status": status,
                "created_at": now,
                "updated_at": updated_at or now,
                "last_login_at": last_login_at,
            }
        )
        return str(result.inserted_id)

    return _create_user
