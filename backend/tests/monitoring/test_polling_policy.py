from __future__ import annotations

from datetime import datetime, timedelta, timezone

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2] / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from cartrap.modules.monitoring.polling_policy import (
    DEFAULT_INTERVAL_MINUTES,
    NEAR_AUCTION_INTERVAL_MINUTES,
    get_poll_interval_minutes,
    is_due_for_poll,
)


def test_polling_policy_uses_fast_interval_near_sale() -> None:
    now = datetime(2026, 3, 11, 12, 0, tzinfo=timezone.utc)
    tracked_lot = {"sale_date": now + timedelta(minutes=30), "last_checked_at": now - timedelta(minutes=2)}

    assert get_poll_interval_minutes(tracked_lot, now) == NEAR_AUCTION_INTERVAL_MINUTES
    assert is_due_for_poll(tracked_lot, now) is True


def test_polling_policy_uses_default_interval_far_from_sale() -> None:
    now = datetime(2026, 3, 11, 12, 0, tzinfo=timezone.utc)
    tracked_lot = {"sale_date": now + timedelta(days=1), "last_checked_at": now - timedelta(minutes=10)}

    assert get_poll_interval_minutes(tracked_lot, now) == DEFAULT_INTERVAL_MINUTES
    assert is_due_for_poll(tracked_lot, now) is False


def test_polling_policy_accepts_configured_intervals() -> None:
    now = datetime(2026, 3, 11, 12, 0, tzinfo=timezone.utc)
    tracked_lot = {"sale_date": now + timedelta(minutes=45), "last_checked_at": now - timedelta(minutes=3)}

    assert (
        get_poll_interval_minutes(
            tracked_lot,
            now,
            default_interval_minutes=20,
            near_auction_interval_minutes=5,
            near_auction_window_hours=1,
        )
        == 5
    )
    assert (
        is_due_for_poll(
            tracked_lot,
            now,
            default_interval_minutes=20,
            near_auction_interval_minutes=5,
            near_auction_window_hours=1,
        )
        is False
    )
