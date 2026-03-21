"""Adaptive polling rules for tracked lots."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


DEFAULT_INTERVAL_MINUTES = 15
NEAR_AUCTION_INTERVAL_MINUTES = 1
NEAR_AUCTION_WINDOW_MINUTES = 120
AUCTION_IMMINENT_WINDOW_MINUTES = 15
RECENT_CHANGE_WINDOW_MINUTES = 180

PRIORITY_ORDER = {
    "auction_imminent": 0,
    "recently_changed": 1,
    "normal": 2,
    "cold": 3,
}


def get_poll_interval_minutes(
    tracked_lot: dict,
    now: datetime | None = None,
    *,
    default_interval_minutes: int = DEFAULT_INTERVAL_MINUTES,
    near_auction_interval_minutes: int = NEAR_AUCTION_INTERVAL_MINUTES,
    near_auction_window_minutes: int = NEAR_AUCTION_WINDOW_MINUTES,
) -> int:
    current_time = now or datetime.now(timezone.utc)
    sale_date = tracked_lot.get("sale_date")
    if sale_date is None:
        return default_interval_minutes

    if sale_date.tzinfo is None:
        sale_date = sale_date.replace(tzinfo=timezone.utc)

    time_until_sale = sale_date - current_time
    if timedelta(0) <= time_until_sale <= timedelta(minutes=near_auction_window_minutes):
        return near_auction_interval_minutes
    return default_interval_minutes


def is_due_for_poll(
    tracked_lot: dict,
    now: datetime | None = None,
    *,
    default_interval_minutes: int = DEFAULT_INTERVAL_MINUTES,
    near_auction_interval_minutes: int = NEAR_AUCTION_INTERVAL_MINUTES,
    near_auction_window_minutes: int = NEAR_AUCTION_WINDOW_MINUTES,
) -> bool:
    current_time = now or datetime.now(timezone.utc)
    last_checked_at = tracked_lot.get("last_checked_at")
    if last_checked_at is None:
        return True
    if last_checked_at.tzinfo is None:
        last_checked_at = last_checked_at.replace(tzinfo=timezone.utc)
    interval = timedelta(
        minutes=get_poll_interval_minutes(
            tracked_lot,
            current_time,
            default_interval_minutes=default_interval_minutes,
            near_auction_interval_minutes=near_auction_interval_minutes,
            near_auction_window_minutes=near_auction_window_minutes,
        )
    )
    return current_time - last_checked_at >= interval


def get_priority_class(
    tracked_lot: dict,
    now: datetime | None = None,
    *,
    near_auction_window_minutes: int = NEAR_AUCTION_WINDOW_MINUTES,
    auction_imminent_window_minutes: int = AUCTION_IMMINENT_WINDOW_MINUTES,
    recent_change_window_minutes: int = RECENT_CHANGE_WINDOW_MINUTES,
) -> str:
    current_time = now or datetime.now(timezone.utc)
    sale_date = tracked_lot.get("sale_date")
    if sale_date is not None:
        if sale_date.tzinfo is None:
            sale_date = sale_date.replace(tzinfo=timezone.utc)
        if sale_date <= current_time + timedelta(minutes=auction_imminent_window_minutes):
            return "auction_imminent"
        if sale_date <= current_time + timedelta(minutes=near_auction_window_minutes):
            return "normal"

    latest_change_at = tracked_lot.get("latest_change_at")
    if latest_change_at is not None and latest_change_at.tzinfo is None:
        latest_change_at = latest_change_at.replace(tzinfo=timezone.utc)
    if tracked_lot.get("has_unseen_update") or (
        latest_change_at is not None and current_time - latest_change_at <= timedelta(minutes=recent_change_window_minutes)
    ):
        return "recently_changed"
    return "cold"


def build_priority_sort_key(
    tracked_lot: dict,
    now: datetime | None = None,
    *,
    near_auction_window_minutes: int = NEAR_AUCTION_WINDOW_MINUTES,
    auction_imminent_window_minutes: int = AUCTION_IMMINENT_WINDOW_MINUTES,
    recent_change_window_minutes: int = RECENT_CHANGE_WINDOW_MINUTES,
) -> tuple[int, float, float, str]:
    current_time = now or datetime.now(timezone.utc)
    priority_class = get_priority_class(
        tracked_lot,
        current_time,
        near_auction_window_minutes=near_auction_window_minutes,
        auction_imminent_window_minutes=auction_imminent_window_minutes,
        recent_change_window_minutes=recent_change_window_minutes,
    )
    sale_date = tracked_lot.get("sale_date")
    sale_timestamp = sale_date.timestamp() if isinstance(sale_date, datetime) else float("inf")
    last_checked_at = tracked_lot.get("last_checked_at")
    checked_timestamp = last_checked_at.timestamp() if isinstance(last_checked_at, datetime) else float("-inf")
    return (PRIORITY_ORDER[priority_class], sale_timestamp, checked_timestamp, str(tracked_lot.get("lot_number", "")))
