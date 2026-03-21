from __future__ import annotations

from datetime import datetime, timedelta, timezone

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2] / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from cartrap.modules.monitoring.polling_policy import (
    build_priority_sort_key,
    DEFAULT_INTERVAL_MINUTES,
    NEAR_AUCTION_INTERVAL_MINUTES,
    get_priority_class,
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
            near_auction_window_minutes=60,
        )
        == 5
    )
    assert (
        is_due_for_poll(
            tracked_lot,
            now,
            default_interval_minutes=20,
            near_auction_interval_minutes=5,
            near_auction_window_minutes=60,
        )
        is False
    )


def test_polling_policy_marks_auction_imminent_and_recently_changed_priorities() -> None:
    now = datetime(2026, 3, 11, 12, 0, tzinfo=timezone.utc)
    auction_imminent = {
        "lot_number": "1",
        "sale_date": now + timedelta(minutes=10),
        "last_checked_at": now - timedelta(minutes=2),
    }
    recently_changed = {
        "lot_number": "2",
        "sale_date": now + timedelta(hours=8),
        "last_checked_at": now - timedelta(minutes=20),
        "has_unseen_update": True,
        "latest_change_at": now - timedelta(minutes=5),
    }
    cold = {
        "lot_number": "3",
        "sale_date": now + timedelta(days=2),
        "last_checked_at": now - timedelta(minutes=20),
    }

    assert get_priority_class(auction_imminent, now) == "auction_imminent"
    assert get_priority_class(recently_changed, now) == "recently_changed"
    assert get_priority_class(cold, now) == "cold"
    assert build_priority_sort_key(auction_imminent, now) < build_priority_sort_key(recently_changed, now)
    assert build_priority_sort_key(recently_changed, now) < build_priority_sort_key(cold, now)
