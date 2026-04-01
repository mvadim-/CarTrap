"""Definitions for admin-managed runtime settings."""

from __future__ import annotations

from typing import List, Literal, Optional, Union

from pydantic import BaseModel, Field


RuntimeSettingValueType = Literal["integer", "integer_list"]
RuntimeSettingValue = Union[int, list[int]]


class RuntimeSettingDefinition(BaseModel):
    key: str
    settings_field: str
    category: str
    label: str
    description: str
    value_type: RuntimeSettingValueType
    restart_required: bool = False
    min_value: Optional[int] = None
    max_value: Optional[int] = None
    min_items: Optional[int] = None
    max_items: Optional[int] = None
    step: int = 1
    unit: Optional[str] = None


class RuntimeSettingRecord(BaseModel):
    key: str
    category: str
    label: str
    description: str
    value_type: RuntimeSettingValueType
    restart_required: bool
    default_value: RuntimeSettingValue
    override_value: Optional[RuntimeSettingValue] = None
    effective_value: RuntimeSettingValue
    updated_by: Optional[str] = None
    updated_at: Optional[str] = None
    min_value: Optional[int] = None
    max_value: Optional[int] = None
    min_items: Optional[int] = None
    max_items: Optional[int] = None
    step: int = 1
    unit: Optional[str] = None
    is_overridden: bool = False


class RuntimeSettingsGroup(BaseModel):
    key: str
    label: str
    items: List[RuntimeSettingRecord] = Field(default_factory=list)


RUNTIME_SETTINGS_GROUP_LABELS: dict[str, str] = {
    "polling": "Polling",
    "freshness": "Freshness",
    "retries": "Retries",
    "invites": "Invites",
}


RUNTIME_SETTING_DEFINITIONS: tuple[RuntimeSettingDefinition, ...] = (
    RuntimeSettingDefinition(
        key="saved_search_poll_interval_minutes",
        settings_field="saved_search_poll_interval_minutes",
        category="polling",
        label="Saved search poll interval",
        description="Minutes between worker refresh checks for saved searches.",
        value_type="integer",
        min_value=1,
        max_value=240,
        unit="minutes",
    ),
    RuntimeSettingDefinition(
        key="watchlist_default_poll_interval_minutes",
        settings_field="watchlist_default_poll_interval_minutes",
        category="polling",
        label="Watchlist default poll interval",
        description="Minutes between refresh checks for tracked lots outside the near-auction window.",
        value_type="integer",
        min_value=1,
        max_value=240,
        unit="minutes",
    ),
    RuntimeSettingDefinition(
        key="watchlist_near_auction_poll_interval_minutes",
        settings_field="watchlist_near_auction_poll_interval_minutes",
        category="polling",
        label="Watchlist near-auction poll interval",
        description="Minutes between refresh checks for tracked lots inside the near-auction window.",
        value_type="integer",
        min_value=1,
        max_value=60,
        unit="minutes",
    ),
    RuntimeSettingDefinition(
        key="watchlist_near_auction_window_minutes",
        settings_field="watchlist_near_auction_window_minutes",
        category="polling",
        label="Watchlist near-auction window",
        description="How many minutes before auction start a tracked lot switches to high-frequency polling.",
        value_type="integer",
        min_value=1,
        max_value=1440,
        unit="minutes",
    ),
    RuntimeSettingDefinition(
        key="live_sync_stale_after_minutes",
        settings_field="live_sync_stale_after_minutes",
        category="freshness",
        label="Live sync stale window",
        description="Minutes before a degraded live-sync failure marker is treated as stale and downgraded to available.",
        value_type="integer",
        min_value=1,
        max_value=240,
        unit="minutes",
    ),
    RuntimeSettingDefinition(
        key="watchlist_auction_reminder_offsets_minutes",
        settings_field="watchlist_auction_reminder_offsets_minutes",
        category="freshness",
        label="Auction reminder offsets",
        description="Minutes before sale time when watchlist auction reminder notifications are sent.",
        value_type="integer_list",
        min_value=0,
        max_value=1440,
        min_items=1,
        max_items=8,
        unit="minutes",
    ),
    RuntimeSettingDefinition(
        key="job_retry_backoff_seconds",
        settings_field="job_retry_backoff_seconds",
        category="retries",
        label="Job retry backoff",
        description="Seconds to wait before retrying a failed worker-managed refresh job.",
        value_type="integer",
        min_value=1,
        max_value=3600,
        unit="seconds",
    ),
    RuntimeSettingDefinition(
        key="invite_ttl_hours",
        settings_field="invite_ttl_hours",
        category="invites",
        label="Invite lifetime",
        description="Hours before a newly created invite expires.",
        value_type="integer",
        min_value=1,
        max_value=720,
        unit="hours",
    ),
)


RUNTIME_SETTING_DEFINITIONS_BY_KEY = {definition.key: definition for definition in RUNTIME_SETTING_DEFINITIONS}


def get_runtime_setting_definition(key: str) -> RuntimeSettingDefinition:
    try:
        return RUNTIME_SETTING_DEFINITIONS_BY_KEY[key]
    except KeyError as exc:
        raise KeyError(f"Runtime setting '{key}' is not allowlisted.") from exc


def list_runtime_setting_definitions() -> tuple[RuntimeSettingDefinition, ...]:
    return RUNTIME_SETTING_DEFINITIONS
