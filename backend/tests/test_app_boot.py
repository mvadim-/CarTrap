from pathlib import Path
import sys

import mongomock
from fastapi.testclient import TestClient
import pytest


ROOT = Path(__file__).resolve().parents[1] / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


import cartrap.app as app_module
from cartrap.app import create_app
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


@pytest.fixture(autouse=True)
def patch_mongo_manager(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(app_module, "MongoManager", FakeMongoManager)


def test_create_app_registers_healthcheck() -> None:
    app = create_app(
        Settings(
            app_name="CarTrap Test API",
            environment="test",
            MONGO_URI="mongodb://localhost:27017",
            MONGO_DB="cartrap_test",
            MONGO_PING_ON_STARTUP=False,
        )
    )

    with TestClient(app) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "CarTrap Test API",
        "environment": "test",
    }


def test_create_app_stores_settings_on_state() -> None:
    settings = Settings(
        app_name="CarTrap State Test",
        environment="test",
        MONGO_URI="mongodb://localhost:27017",
        MONGO_DB="cartrap_test",
        MONGO_PING_ON_STARTUP=False,
    )

    app = create_app(settings)

    assert app.state.settings.app_name == "CarTrap State Test"
    assert app.state.settings.mongo_db == "cartrap_test"
