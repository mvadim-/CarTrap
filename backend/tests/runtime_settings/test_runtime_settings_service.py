from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys

from fastapi import HTTPException
import mongomock
import pytest


ROOT = Path(__file__).resolve().parents[2] / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from cartrap.config import Settings
from cartrap.modules.runtime_settings.service import RuntimeSettingsService


def test_runtime_settings_service_lists_env_defaults() -> None:
    database = mongomock.MongoClient(tz_aware=True)["cartrap_test"]
    settings = Settings(
        saved_search_poll_interval_minutes=22,
        watchlist_default_poll_interval_minutes=18,
        watchlist_near_auction_poll_interval_minutes=3,
        watchlist_near_auction_window_minutes=240,
        live_sync_stale_after_minutes=12,
        job_retry_backoff_seconds=90,
        watchlist_auction_reminder_offsets_minutes=[90, 30, 0],
        invite_ttl_hours=96,
    )
    service = RuntimeSettingsService(database, settings)

    items = service.list_settings()
    items_by_key = {item["key"]: item for item in items}

    assert items_by_key["saved_search_poll_interval_minutes"]["default_value"] == 22
    assert items_by_key["saved_search_poll_interval_minutes"]["effective_value"] == 22
    assert items_by_key["saved_search_poll_interval_minutes"]["is_overridden"] is False
    assert items_by_key["watchlist_auction_reminder_offsets_minutes"]["default_value"] == [90, 30, 0]
    assert items_by_key["watchlist_auction_reminder_offsets_minutes"]["effective_value"] == [90, 30, 0]
    assert items_by_key["job_retry_backoff_seconds"]["default_value"] == 90
    assert items_by_key["invite_ttl_hours"]["default_value"] == 96


def test_runtime_settings_service_persists_override_and_reset() -> None:
    database = mongomock.MongoClient(tz_aware=True)["cartrap_test"]
    settings = Settings()
    now = datetime(2026, 4, 1, 16, 30, tzinfo=timezone.utc)
    service = RuntimeSettingsService(database, settings, now_provider=lambda: now)

    service.update_settings(
        {
            "saved_search_poll_interval_minutes": 7,
            "watchlist_auction_reminder_offsets_minutes": [15, 45, 15, 0],
        },
        updated_by="admin-user-1",
    )

    items_by_key = {item["key"]: item for item in service.list_settings()}
    assert service.get_effective_value("saved_search_poll_interval_minutes") == 7
    assert items_by_key["saved_search_poll_interval_minutes"]["override_value"] == 7
    assert items_by_key["saved_search_poll_interval_minutes"]["updated_by"] == "admin-user-1"
    assert items_by_key["saved_search_poll_interval_minutes"]["updated_at"] == "2026-04-01T16:30:00Z"
    assert items_by_key["watchlist_auction_reminder_offsets_minutes"]["effective_value"] == [45, 15, 0]

    service.reset_settings(["saved_search_poll_interval_minutes"])

    reset_items_by_key = {item["key"]: item for item in service.list_settings()}
    assert service.get_effective_value("saved_search_poll_interval_minutes") == settings.saved_search_poll_interval_minutes
    assert reset_items_by_key["saved_search_poll_interval_minutes"]["override_value"] is None
    assert reset_items_by_key["saved_search_poll_interval_minutes"]["is_overridden"] is False


def test_runtime_settings_service_rejects_invalid_values_and_disallowed_keys() -> None:
    database = mongomock.MongoClient(tz_aware=True)["cartrap_test"]
    service = RuntimeSettingsService(database, Settings())

    with pytest.raises(HTTPException) as invalid_integer:
        service.update_settings({"job_retry_backoff_seconds": 0}, updated_by="admin-user-1")
    assert invalid_integer.value.status_code == 422

    with pytest.raises(HTTPException) as invalid_list:
        service.update_settings({"watchlist_auction_reminder_offsets_minutes": []}, updated_by="admin-user-1")
    assert invalid_list.value.status_code == 422

    with pytest.raises(HTTPException) as disallowed_key:
        service.update_settings({"jwt_secret": 123}, updated_by="admin-user-1")
    assert disallowed_key.value.status_code == 400


def test_runtime_settings_service_falls_back_when_persisted_override_is_invalid() -> None:
    database = mongomock.MongoClient(tz_aware=True)["cartrap_test"]
    settings = Settings(invite_ttl_hours=72)
    service = RuntimeSettingsService(database, settings)

    database["admin_runtime_settings"].insert_one(
        {
            "key": "invite_ttl_hours",
            "value": 0,
            "value_type": "integer",
            "updated_by": "legacy-admin",
            "updated_at": datetime(2026, 4, 1, 12, 0, tzinfo=timezone.utc),
        }
    )

    assert service.get_effective_value("invite_ttl_hours") == 72
