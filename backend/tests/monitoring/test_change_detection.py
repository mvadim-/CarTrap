from __future__ import annotations

from datetime import datetime, timezone

from pathlib import Path
import sys

import mongomock


ROOT = Path(__file__).resolve().parents[2] / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from cartrap.modules.copart_provider.models import CopartLotSnapshot
from cartrap.modules.monitoring.change_detection import detect_significant_changes
from cartrap.modules.monitoring.service import MonitoringService
from cartrap.modules.watchlist.service import WatchlistService


class FakeProvider:
    def __init__(self, snapshots: list[CopartLotSnapshot] | None = None, should_fail: bool = False) -> None:
        self._snapshots = snapshots or []
        self._should_fail = should_fail
        self._index = 0

    def fetch_lot(self, url: str) -> CopartLotSnapshot:
        if self._should_fail:
            raise RuntimeError("provider failure")
        snapshot = self._snapshots[min(self._index, len(self._snapshots) - 1)]
        self._index += 1
        return snapshot

    def close(self) -> None:
        return None


def test_detect_significant_changes_returns_only_changed_fields() -> None:
    previous = {
        "status": "upcoming",
        "raw_status": "Upcoming",
        "sale_date": datetime(2026, 3, 20, 17, 0, tzinfo=timezone.utc),
        "current_bid": 1200.0,
        "buy_now_price": None,
        "currency": "USD",
    }
    current = {
        "status": "live",
        "raw_status": "Live",
        "sale_date": datetime(2026, 3, 20, 17, 0, tzinfo=timezone.utc),
        "current_bid": 1800.0,
        "buy_now_price": None,
        "currency": "USD",
    }

    changes = detect_significant_changes(previous, current)

    assert set(changes.keys()) == {"status", "raw_status", "current_bid"}


def test_monitoring_service_stores_new_snapshot_when_state_changes() -> None:
    database = mongomock.MongoClient(tz_aware=True)["cartrap_test"]
    initial_snapshot = CopartLotSnapshot(
        lot_number="12345678",
        title="2020 TOYOTA CAMRY SE",
        url="https://www.copart.com/lot/12345678",
        status="upcoming",
        raw_status="Upcoming",
        sale_date=datetime(2026, 3, 20, 17, 0, tzinfo=timezone.utc),
        current_bid=1000.0,
        buy_now_price=None,
        currency="USD",
    )
    watchlist_service = WatchlistService(database, provider_factory=lambda: FakeProvider([initial_snapshot]))
    created = watchlist_service.add_tracked_lot({"id": "user-1"}, "https://www.copart.com/lot/12345678")

    changed_snapshot = CopartLotSnapshot(
        lot_number="12345678",
        title="2020 TOYOTA CAMRY SE",
        url="https://www.copart.com/lot/12345678",
        status="live",
        raw_status="Live",
        sale_date=datetime(2026, 3, 20, 17, 0, tzinfo=timezone.utc),
        current_bid=1800.0,
        buy_now_price=None,
        currency="USD",
    )
    monitoring = MonitoringService(database, provider_factory=lambda: FakeProvider([changed_snapshot]))

    result = monitoring.poll_due_lots(now=datetime(2026, 3, 20, 16, 30, tzinfo=timezone.utc))

    assert result["processed"] == 1
    assert result["updated"] == 1
    assert result["failed"] == 0
    assert result["events"][0]["tracked_lot_id"] == created["tracked_lot"]["id"]
    assert database["lot_snapshots"].count_documents({"tracked_lot_id": created["tracked_lot"]["id"]}) == 2


def test_monitoring_service_counts_failures_without_overwriting_state() -> None:
    database = mongomock.MongoClient(tz_aware=True)["cartrap_test"]
    initial_snapshot = CopartLotSnapshot(
        lot_number="87654321",
        title="2018 HONDA CIVIC EX",
        url="https://www.copart.com/lot/87654321",
        status="upcoming",
        raw_status="Upcoming",
        sale_date=datetime(2026, 3, 20, 17, 0, tzinfo=timezone.utc),
        current_bid=1800.0,
        buy_now_price=None,
        currency="USD",
    )
    watchlist_service = WatchlistService(database, provider_factory=lambda: FakeProvider([initial_snapshot]))
    created = watchlist_service.add_tracked_lot({"id": "user-2"}, "https://www.copart.com/lot/87654321")
    monitoring = MonitoringService(database, provider_factory=lambda: FakeProvider(should_fail=True))

    result = monitoring.poll_due_lots(now=datetime(2026, 3, 20, 16, 30, tzinfo=timezone.utc))
    tracked_lot = database["tracked_lots"].find_one({"lot_number": "87654321"})

    assert result["processed"] == 1
    assert result["updated"] == 0
    assert result["failed"] == 1
    assert tracked_lot["status"] == "upcoming"
    assert database["lot_snapshots"].count_documents({"tracked_lot_id": created["tracked_lot"]["id"]}) == 1
