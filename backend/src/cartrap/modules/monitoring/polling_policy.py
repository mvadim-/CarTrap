"""Adaptive polling rules for tracked lots."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


DEFAULT_INTERVAL_MINUTES = 15
NEAR_AUCTION_INTERVAL_MINUTES = 1
NEAR_AUCTION_WINDOW_HOURS = 2


def get_poll_interval_minutes(
    tracked_lot: dict,
    now: datetime | None = None,
    *,
    default_interval_minutes: int = DEFAULT_INTERVAL_MINUTES,
    near_auction_interval_minutes: int = NEAR_AUCTION_INTERVAL_MINUTES,
    near_auction_window_hours: int = NEAR_AUCTION_WINDOW_HOURS,
) -> int:
    current_time = now or datetime.now(timezone.utc)
    sale_date = tracked_lot.get("sale_date")
    if sale_date is None:
        return default_interval_minutes

    if sale_date.tzinfo is None:
        sale_date = sale_date.replace(tzinfo=timezone.utc)

    time_until_sale = sale_date - current_time
    if timedelta(0) <= time_until_sale <= timedelta(hours=near_auction_window_hours):
        return near_auction_interval_minutes
    return default_interval_minutes


def is_due_for_poll(
    tracked_lot: dict,
    now: datetime | None = None,
    *,
    default_interval_minutes: int = DEFAULT_INTERVAL_MINUTES,
    near_auction_interval_minutes: int = NEAR_AUCTION_INTERVAL_MINUTES,
    near_auction_window_hours: int = NEAR_AUCTION_WINDOW_HOURS,
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
            near_auction_window_hours=near_auction_window_hours,
        )
    )
    return current_time - last_checked_at >= interval
