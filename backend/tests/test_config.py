from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1] / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from pydantic import ValidationError

from cartrap.config import Settings, get_settings


def test_settings_load_values_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("APP_NAME", "CarTrap Local")
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("API_PREFIX", "/internal")
    monkeypatch.setenv("BACKEND_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    monkeypatch.setenv("MONGO_URI", "mongodb://example:27017")
    monkeypatch.setenv("MONGO_DB", "cartrap_local")
    monkeypatch.setenv("MONGO_PING_ON_STARTUP", "true")

    settings = Settings()

    assert settings.app_name == "CarTrap Local"
    assert settings.environment == "test"
    assert settings.api_prefix == "/internal"
    assert settings.cors_origins == ["http://localhost:5173", "http://127.0.0.1:5173"]
    assert settings.mongo_uri == "mongodb://example:27017"
    assert settings.mongo_db == "cartrap_local"
    assert settings.mongo_ping_on_startup is True


def test_get_settings_caches_instance() -> None:
    get_settings.cache_clear()

    first = get_settings()
    second = get_settings()

    assert first is second


def test_settings_reject_empty_mongo_uri() -> None:
    with pytest.raises(ValidationError):
        Settings(MONGO_URI="")
