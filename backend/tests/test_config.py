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
    monkeypatch.setenv("SAVED_SEARCH_POLL_INTERVAL_MINUTES", "20")
    monkeypatch.setenv("WATCHLIST_DEFAULT_POLL_INTERVAL_MINUTES", "25")
    monkeypatch.setenv("WATCHLIST_NEAR_AUCTION_POLL_INTERVAL_MINUTES", "2")
    monkeypatch.setenv("WATCHLIST_NEAR_AUCTION_WINDOW_MINUTES", "180")
    monkeypatch.setenv("LIVE_SYNC_STALE_AFTER_MINUTES", "12")
    monkeypatch.setenv("JOB_RETRY_BACKOFF_SECONDS", "75")
    monkeypatch.setenv("WATCHLIST_AUCTION_REMINDER_OFFSETS_MINUTES", "90,30,0")
    monkeypatch.setenv("COPART_API_BASE_URL", "https://mmember.copart.com")
    monkeypatch.setenv("COPART_API_SEARCH_PATH", "/srch/?services=bidIncrementsBySiteV2")
    monkeypatch.setenv("COPART_API_SEARCH_KEYWORDS_PATH", "/mcs/v2/public/data/search/keywords")
    monkeypatch.setenv("COPART_API_LOT_DETAILS_PATH", "/lots-api/v1/lot-details?services=bidIncrementsBySiteV2")
    monkeypatch.setenv("COPART_API_DEVICE_NAME", "iPhone 15 Pro Max")
    monkeypatch.setenv("COPART_API_D_TOKEN", "token-123")
    monkeypatch.setenv("COPART_API_COOKIE", "SessionID=abc")
    monkeypatch.setenv("COPART_API_SITECODE", "CPRTUS")
    monkeypatch.setenv("COPART_CONNECTOR_LOGIN_PATH", "/mds-api/v1/member/login")
    monkeypatch.setenv("COPART_CONNECTOR_ENCRYPTION_KEY_VERSION", "v2")
    monkeypatch.setenv("COPART_CONNECTOR_SESSION_EXPIRING_THRESHOLD_MINUTES", "45")

    settings = Settings()

    assert settings.app_name == "CarTrap Local"
    assert settings.environment == "test"
    assert settings.api_prefix == "/internal"
    assert settings.cors_origins == ["http://localhost:5173", "http://127.0.0.1:5173"]
    assert settings.cors_origin_regex is not None
    assert settings.mongo_uri == "mongodb://example:27017"
    assert settings.mongo_db == "cartrap_local"
    assert settings.mongo_ping_on_startup is True
    assert settings.saved_search_poll_interval_minutes == 20
    assert settings.watchlist_default_poll_interval_minutes == 25
    assert settings.watchlist_near_auction_poll_interval_minutes == 2
    assert settings.watchlist_near_auction_window_minutes == 180
    assert settings.live_sync_stale_after_minutes == 12
    assert settings.job_retry_backoff_seconds == 75
    assert settings.watchlist_auction_reminder_offsets_minutes == [90, 30, 0]
    assert settings.copart_api_base_url == "https://mmember.copart.com"
    assert settings.copart_api_search_path == "/srch/?services=bidIncrementsBySiteV2"
    assert settings.copart_api_search_keywords_path == "/mcs/v2/public/data/search/keywords"
    assert settings.copart_api_lot_details_path == "/lots-api/v1/lot-details?services=bidIncrementsBySiteV2"
    assert settings.copart_api_device_name == "iPhone 15 Pro Max"
    assert settings.copart_api_d_token == "token-123"
    assert settings.copart_api_cookie == "SessionID=abc"
    assert settings.copart_api_site_code == "CPRTUS"
    assert settings.copart_connector_login_path == "/mds-api/v1/member/login"
    assert settings.copart_connector_encryption_key_version == "v2"
    assert settings.copart_connector_session_expiring_threshold_minutes == 45


def test_get_settings_caches_instance() -> None:
    get_settings.cache_clear()

    first = get_settings()
    second = get_settings()

    assert first is second


def test_settings_reject_empty_mongo_uri() -> None:
    with pytest.raises(ValidationError):
        Settings(MONGO_URI="")


def test_settings_disable_default_cors_regex_in_production() -> None:
    settings = Settings(environment="production")

    assert settings.cors_origin_regex is None


def test_settings_reject_blank_connector_encryption_key() -> None:
    with pytest.raises(ValidationError):
        Settings(COPART_CONNECTOR_ENCRYPTION_KEY=" ")


def test_settings_reject_negative_watchlist_reminder_offsets() -> None:
    with pytest.raises(ValidationError):
        Settings(WATCHLIST_AUCTION_REMINDER_OFFSETS_MINUTES="-15,0")
