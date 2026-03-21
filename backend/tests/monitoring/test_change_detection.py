from __future__ import annotations

from datetime import datetime, timedelta, timezone

from pathlib import Path
import sys

from bson import ObjectId
import mongomock


ROOT = Path(__file__).resolve().parents[2] / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from cartrap.modules.copart_provider.errors import CopartGatewayUnavailableError
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


class EtagAwareProvider:
    def __init__(self, snapshot: CopartLotSnapshot | None, *, not_modified: bool, etag: str | None) -> None:
        self._snapshot = snapshot
        self._not_modified = not_modified
        self._etag = etag

    def fetch_lot_conditional(self, url: str, etag: str | None = None):
        del url
        del etag
        return type(
            "FetchResult",
            (),
            {"snapshot": self._snapshot, "etag": self._etag, "not_modified": self._not_modified},
        )()

    def close(self) -> None:
        return None


class GatewayUnavailableProvider:
    def fetch_lot(self, url: str) -> CopartLotSnapshot:
        del url
        raise CopartGatewayUnavailableError("gateway unavailable")

    def close(self) -> None:
        return None


class FakeNotificationService:
    def __init__(self) -> None:
        self.change_events: list[dict] = []
        self.reminder_events: list[dict] = []

    def send_lot_change_notification(self, event: dict) -> dict:
        self.change_events.append(event)
        return {"delivered": 0, "failed": 0, "removed": 0, "endpoints": []}

    def send_auction_reminder_notification(self, event: dict) -> dict:
        self.reminder_events.append(event)
        return {"delivered": 0, "failed": 0, "removed": 0, "endpoints": []}


def _mark_due(database, tracked_lot_id: str, now: datetime, *, minutes: int = 20) -> None:
    database["tracked_lots"].update_one(
        {"_id": ObjectId(tracked_lot_id)},
        {"$set": {"last_checked_at": now - timedelta(minutes=minutes)}},
    )


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
        thumbnail_url=None,
        image_urls=[],
        odometer="10,000 ACTUAL",
        primary_damage="FRONT END",
        estimated_retail_value=35500.0,
        has_key=False,
        drivetrain="FWD",
        highlights=["Run and Drive"],
        vin="1FA6P8TH0J5100001",
        status="upcoming",
        raw_status="Upcoming",
        sale_date=datetime(2026, 3, 20, 17, 0, tzinfo=timezone.utc),
        current_bid=1000.0,
        buy_now_price=None,
        currency="USD",
    )
    watchlist_service = WatchlistService(database, provider_factory=lambda: FakeProvider([initial_snapshot]))
    created = watchlist_service.add_tracked_lot({"id": "user-1"}, "https://www.copart.com/lot/12345678")
    _mark_due(database, created["tracked_lot"]["id"], datetime(2026, 3, 20, 16, 30, tzinfo=timezone.utc))

    changed_snapshot = CopartLotSnapshot(
        lot_number="12345678",
        title="2020 TOYOTA CAMRY SE",
        url="https://www.copart.com/lot/12345678",
        thumbnail_url="https://img.copart.com/12345678-detail.jpg",
        image_urls=[
            "https://img.copart.com/12345678-detail.jpg",
            "https://img.copart.com/12345678-detail-2.jpg",
        ],
        odometer="12,345 ACTUAL",
        primary_damage="REAR END",
        estimated_retail_value=36500.0,
        has_key=True,
        drivetrain="AWD",
        highlights=["Enhanced Vehicles"],
        vin="1FA6P8TH0J5100002",
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
    tracked_lot = database["tracked_lots"].find_one({"lot_number": "12345678"})
    assert tracked_lot["thumbnail_url"] == "https://img.copart.com/12345678-detail.jpg"
    assert tracked_lot["image_urls"] == [
        "https://img.copart.com/12345678-detail.jpg",
        "https://img.copart.com/12345678-detail-2.jpg",
    ]
    assert tracked_lot["odometer"] == "12,345 ACTUAL"
    assert tracked_lot["primary_damage"] == "REAR END"
    assert tracked_lot["estimated_retail_value"] == 36500.0
    assert tracked_lot["has_key"] is True
    assert tracked_lot["drivetrain"] == "AWD"
    assert tracked_lot["highlights"] == ["Enhanced Vehicles"]
    assert tracked_lot["vin"] == "1FA6P8TH0J5100002"
    assert tracked_lot["has_unseen_update"] is True
    assert tracked_lot["latest_change_at"] == datetime(2026, 3, 20, 16, 30, tzinfo=timezone.utc)
    assert tracked_lot["latest_changes"]["raw_status"] == {"before": "Upcoming", "after": "Live"}
    assert tracked_lot["latest_changes"]["current_bid"] == {"before": 1000.0, "after": 1800.0}
    assert tracked_lot["last_refresh_priority_class"] == "normal"
    assert tracked_lot["last_refresh_change_count"] == 3
    assert tracked_lot["last_refresh_reminder_count"] == 1


def test_monitoring_service_counts_failures_without_overwriting_state() -> None:
    database = mongomock.MongoClient(tz_aware=True)["cartrap_test"]
    initial_snapshot = CopartLotSnapshot(
        lot_number="87654321",
        title="2018 HONDA CIVIC EX",
        url="https://www.copart.com/lot/87654321",
        thumbnail_url=None,
        image_urls=[],
        odometer=None,
        primary_damage=None,
        estimated_retail_value=None,
        has_key=None,
        drivetrain=None,
        highlights=[],
        vin=None,
        status="upcoming",
        raw_status="Upcoming",
        sale_date=datetime(2026, 3, 20, 17, 0, tzinfo=timezone.utc),
        current_bid=1800.0,
        buy_now_price=None,
        currency="USD",
    )
    watchlist_service = WatchlistService(database, provider_factory=lambda: FakeProvider([initial_snapshot]))
    created = watchlist_service.add_tracked_lot({"id": "user-2"}, "https://www.copart.com/lot/87654321")
    _mark_due(database, created["tracked_lot"]["id"], datetime(2026, 3, 20, 16, 30, tzinfo=timezone.utc))
    monitoring = MonitoringService(database, provider_factory=lambda: FakeProvider(should_fail=True))

    result = monitoring.poll_due_lots(now=datetime(2026, 3, 20, 16, 30, tzinfo=timezone.utc))
    tracked_lot = database["tracked_lots"].find_one({"lot_number": "87654321"})

    assert result["processed"] == 1
    assert result["updated"] == 0
    assert result["failed"] == 1
    assert tracked_lot["status"] == "upcoming"
    assert database["lot_snapshots"].count_documents({"tracked_lot_id": created["tracked_lot"]["id"]}) == 1


def test_monitoring_service_skips_snapshot_creation_when_lot_etag_is_not_modified() -> None:
    database = mongomock.MongoClient(tz_aware=True)["cartrap_test"]
    initial_snapshot = CopartLotSnapshot(
        lot_number="12345678",
        title="2020 TOYOTA CAMRY SE",
        url="https://www.copart.com/lot/12345678",
        thumbnail_url=None,
        image_urls=[],
        odometer="10,000 ACTUAL",
        primary_damage="FRONT END",
        estimated_retail_value=35500.0,
        has_key=False,
        drivetrain="FWD",
        highlights=["Run and Drive"],
        vin="1FA6P8TH0J5100001",
        status="upcoming",
        raw_status="Upcoming",
        sale_date=datetime(2026, 3, 20, 17, 0, tzinfo=timezone.utc),
        current_bid=1000.0,
        buy_now_price=None,
        currency="USD",
    )
    watchlist_service = WatchlistService(database, provider_factory=lambda: FakeProvider([initial_snapshot]))
    created = watchlist_service.add_tracked_lot({"id": "user-4"}, "https://www.copart.com/lot/12345678")
    _mark_due(database, created["tracked_lot"]["id"], datetime(2026, 3, 20, 16, 30, tzinfo=timezone.utc))
    database["tracked_lots"].update_one(
        {"_id": ObjectId(created["tracked_lot"]["id"])},
        {"$set": {"detail_etag": "\"lot-etag-1\""}},
    )
    monitoring = MonitoringService(
        database,
        provider_factory=lambda: EtagAwareProvider(None, not_modified=True, etag="\"lot-etag-2\""),
    )

    result = monitoring.poll_due_lots(now=datetime(2026, 3, 20, 16, 30, tzinfo=timezone.utc))

    assert result["processed"] == 1
    assert result["updated"] == 0
    assert result["failed"] == 0
    tracked_lot = database["tracked_lots"].find_one({"_id": ObjectId(created["tracked_lot"]["id"])})
    assert tracked_lot["detail_etag"] == "\"lot-etag-2\""
    assert tracked_lot["last_checked_at"] == datetime(2026, 3, 20, 16, 30, tzinfo=timezone.utc)
    assert tracked_lot["has_unseen_update"] is False
    assert database["lot_snapshots"].count_documents({"tracked_lot_id": created["tracked_lot"]["id"]}) == 1


def test_monitoring_service_treats_gateway_unavailable_as_transient_failure() -> None:
    database = mongomock.MongoClient(tz_aware=True)["cartrap_test"]
    initial_snapshot = CopartLotSnapshot(
        lot_number="87654321",
        title="2018 HONDA CIVIC EX",
        url="https://www.copart.com/lot/87654321",
        thumbnail_url=None,
        image_urls=[],
        odometer=None,
        primary_damage=None,
        estimated_retail_value=None,
        has_key=None,
        drivetrain=None,
        highlights=[],
        vin=None,
        status="upcoming",
        raw_status="Upcoming",
        sale_date=datetime(2026, 3, 20, 17, 0, tzinfo=timezone.utc),
        current_bid=1800.0,
        buy_now_price=None,
        currency="USD",
    )
    watchlist_service = WatchlistService(database, provider_factory=lambda: FakeProvider([initial_snapshot]))
    created = watchlist_service.add_tracked_lot({"id": "user-5"}, "https://www.copart.com/lot/87654321")
    _mark_due(database, created["tracked_lot"]["id"], datetime(2026, 3, 20, 16, 30, tzinfo=timezone.utc))
    monitoring = MonitoringService(database, provider_factory=lambda: GatewayUnavailableProvider())

    result = monitoring.poll_due_lots(now=datetime(2026, 3, 20, 16, 30, tzinfo=timezone.utc))

    assert result["processed"] == 1
    assert result["updated"] == 0
    assert result["failed"] == 1
    tracked_lot = database["tracked_lots"].find_one({"_id": ObjectId(created["tracked_lot"]["id"])})
    assert tracked_lot["status"] == "upcoming"
    assert tracked_lot["last_checked_at"] < datetime(2026, 3, 20, 16, 30, tzinfo=timezone.utc)
    assert database["lot_snapshots"].count_documents({"tracked_lot_id": created["tracked_lot"]["id"]}) == 1


def test_monitoring_service_sends_auction_reminders_once_per_threshold_for_unchanged_lot() -> None:
    database = mongomock.MongoClient(tz_aware=True)["cartrap_test"]
    notification_service = FakeNotificationService()
    initial_snapshot = CopartLotSnapshot(
        lot_number="12345678",
        title="2020 TOYOTA CAMRY SE",
        url="https://www.copart.com/lot/12345678",
        thumbnail_url=None,
        image_urls=[],
        odometer="10,000 ACTUAL",
        primary_damage="FRONT END",
        estimated_retail_value=35500.0,
        has_key=False,
        drivetrain="FWD",
        highlights=["Run and Drive"],
        vin="1FA6P8TH0J5100001",
        status="upcoming",
        raw_status="Upcoming",
        sale_date=datetime(2026, 3, 20, 17, 0, tzinfo=timezone.utc),
        current_bid=1000.0,
        buy_now_price=None,
        currency="USD",
    )
    watchlist_service = WatchlistService(database, provider_factory=lambda: FakeProvider([initial_snapshot]))
    created = watchlist_service.add_tracked_lot({"id": "user-6"}, "https://www.copart.com/lot/12345678")
    _mark_due(database, created["tracked_lot"]["id"], datetime(2026, 3, 20, 16, 0, tzinfo=timezone.utc))
    database["tracked_lots"].update_one(
        {"_id": ObjectId(created["tracked_lot"]["id"])},
        {"$set": {"detail_etag": "\"lot-etag-1\""}},
    )
    monitoring = MonitoringService(
        database,
        provider_factory=lambda: EtagAwareProvider(None, not_modified=True, etag="\"lot-etag-2\""),
        notification_service=notification_service,
    )

    result_one = monitoring.poll_due_lots(now=datetime(2026, 3, 20, 16, 0, tzinfo=timezone.utc))
    result_two = monitoring.poll_due_lots(now=datetime(2026, 3, 20, 16, 5, tzinfo=timezone.utc))
    result_three = monitoring.poll_due_lots(now=datetime(2026, 3, 20, 16, 45, tzinfo=timezone.utc))
    result_four = monitoring.poll_due_lots(now=datetime(2026, 3, 20, 17, 1, tzinfo=timezone.utc))

    assert result_one["reminded"] == 1
    assert result_two["reminded"] == 0
    assert result_three["reminded"] == 1
    assert result_four["reminded"] == 1
    assert [event["reminder_offset_minutes"] for event in notification_service.reminder_events] == [60, 15, 0]
    tracked_lot = database["tracked_lots"].find_one({"_id": ObjectId(created["tracked_lot"]["id"])})
    assert tracked_lot["auction_reminder_sent_minutes"] == [60, 15, 0]
    assert tracked_lot["last_refresh_priority_class"] == "auction_imminent"


def test_monitoring_service_resets_auction_reminders_when_sale_date_changes() -> None:
    database = mongomock.MongoClient(tz_aware=True)["cartrap_test"]
    notification_service = FakeNotificationService()
    initial_snapshot = CopartLotSnapshot(
        lot_number="12345678",
        title="2020 TOYOTA CAMRY SE",
        url="https://www.copart.com/lot/12345678",
        thumbnail_url=None,
        image_urls=[],
        odometer="10,000 ACTUAL",
        primary_damage="FRONT END",
        estimated_retail_value=35500.0,
        has_key=False,
        drivetrain="FWD",
        highlights=["Run and Drive"],
        vin="1FA6P8TH0J5100001",
        status="upcoming",
        raw_status="Upcoming",
        sale_date=datetime(2026, 3, 20, 17, 0, tzinfo=timezone.utc),
        current_bid=1000.0,
        buy_now_price=None,
        currency="USD",
    )
    watchlist_service = WatchlistService(database, provider_factory=lambda: FakeProvider([initial_snapshot]))
    created = watchlist_service.add_tracked_lot({"id": "user-7"}, "https://www.copart.com/lot/12345678")
    tracked_lot_id = created["tracked_lot"]["id"]
    _mark_due(database, tracked_lot_id, datetime(2026, 3, 20, 16, 0, tzinfo=timezone.utc))
    database["tracked_lots"].update_one(
        {"_id": ObjectId(tracked_lot_id)},
        {"$set": {"detail_etag": "\"lot-etag-1\""}},
    )

    unchanged_monitoring = MonitoringService(
        database,
        provider_factory=lambda: EtagAwareProvider(None, not_modified=True, etag="\"lot-etag-2\""),
        notification_service=notification_service,
    )
    unchanged_monitoring.poll_due_lots(now=datetime(2026, 3, 20, 16, 0, tzinfo=timezone.utc))

    rescheduled_snapshot = CopartLotSnapshot(
        lot_number="12345678",
        title="2020 TOYOTA CAMRY SE",
        url="https://www.copart.com/lot/12345678",
        thumbnail_url=None,
        image_urls=[],
        odometer="10,000 ACTUAL",
        primary_damage="FRONT END",
        estimated_retail_value=35500.0,
        has_key=False,
        drivetrain="FWD",
        highlights=["Run and Drive"],
        vin="1FA6P8TH0J5100001",
        status="upcoming",
        raw_status="Upcoming",
        sale_date=datetime(2026, 3, 20, 18, 30, tzinfo=timezone.utc),
        current_bid=1000.0,
        buy_now_price=None,
        currency="USD",
    )
    changed_monitoring = MonitoringService(
        database,
        provider_factory=lambda: FakeProvider([rescheduled_snapshot]),
        notification_service=notification_service,
    )

    changed_result = changed_monitoring.poll_due_lots(now=datetime(2026, 3, 20, 16, 10, tzinfo=timezone.utc))
    resumed_result = unchanged_monitoring.poll_due_lots(now=datetime(2026, 3, 20, 17, 30, tzinfo=timezone.utc))

    assert changed_result["updated"] == 1
    assert changed_result["reminded"] == 0
    assert resumed_result["reminded"] == 1
    assert [event["reminder_offset_minutes"] for event in notification_service.reminder_events] == [60, 60]
    tracked_lot = database["tracked_lots"].find_one({"_id": ObjectId(tracked_lot_id)})
    assert tracked_lot["sale_date"] == datetime(2026, 3, 20, 18, 30, tzinfo=timezone.utc)
    assert tracked_lot["auction_reminder_sale_date"] == datetime(2026, 3, 20, 18, 30, tzinfo=timezone.utc)
    assert tracked_lot["auction_reminder_sent_minutes"] == [60]


def test_monitoring_service_polls_when_reminder_threshold_crosses_before_standard_interval() -> None:
    database = mongomock.MongoClient(tz_aware=True)["cartrap_test"]
    notification_service = FakeNotificationService()
    initial_snapshot = CopartLotSnapshot(
        lot_number="12345678",
        title="2020 TOYOTA CAMRY SE",
        url="https://www.copart.com/lot/12345678",
        thumbnail_url=None,
        image_urls=[],
        odometer="10,000 ACTUAL",
        primary_damage="FRONT END",
        estimated_retail_value=35500.0,
        has_key=False,
        drivetrain="FWD",
        highlights=["Run and Drive"],
        vin="1FA6P8TH0J5100001",
        status="upcoming",
        raw_status="Upcoming",
        sale_date=datetime(2026, 3, 20, 17, 0, tzinfo=timezone.utc),
        current_bid=1000.0,
        buy_now_price=None,
        currency="USD",
    )
    watchlist_service = WatchlistService(database, provider_factory=lambda: FakeProvider([initial_snapshot]))
    created = watchlist_service.add_tracked_lot({"id": "user-8"}, "https://www.copart.com/lot/12345678")
    database["tracked_lots"].update_one(
        {"_id": ObjectId(created["tracked_lot"]["id"])},
        {
            "$set": {
                "detail_etag": "\"lot-etag-1\"",
                "last_checked_at": datetime(2026, 3, 20, 15, 50, tzinfo=timezone.utc),
            }
        },
    )
    monitoring = MonitoringService(
        database,
        provider_factory=lambda: EtagAwareProvider(None, not_modified=True, etag="\"lot-etag-2\""),
        notification_service=notification_service,
        default_poll_interval_minutes=30,
        near_auction_poll_interval_minutes=30,
        near_auction_window_minutes=10,
    )

    result = monitoring.poll_due_lots(now=datetime(2026, 3, 20, 16, 1, tzinfo=timezone.utc))

    assert result["processed"] == 1
    assert result["reminded"] == 1
    assert notification_service.reminder_events[0]["reminder_offset_minutes"] == 60


def test_monitoring_service_polls_for_auction_start_reminder_after_recent_pre_start_check() -> None:
    database = mongomock.MongoClient(tz_aware=True)["cartrap_test"]
    notification_service = FakeNotificationService()
    initial_snapshot = CopartLotSnapshot(
        lot_number="12345678",
        title="2020 TOYOTA CAMRY SE",
        url="https://www.copart.com/lot/12345678",
        thumbnail_url=None,
        image_urls=[],
        odometer="10,000 ACTUAL",
        primary_damage="FRONT END",
        estimated_retail_value=35500.0,
        has_key=False,
        drivetrain="FWD",
        highlights=["Run and Drive"],
        vin="1FA6P8TH0J5100001",
        status="upcoming",
        raw_status="Upcoming",
        sale_date=datetime(2026, 3, 20, 17, 0, tzinfo=timezone.utc),
        current_bid=1000.0,
        buy_now_price=None,
        currency="USD",
    )
    watchlist_service = WatchlistService(database, provider_factory=lambda: FakeProvider([initial_snapshot]))
    created = watchlist_service.add_tracked_lot({"id": "user-9"}, "https://www.copart.com/lot/12345678")
    database["tracked_lots"].update_one(
        {"_id": ObjectId(created["tracked_lot"]["id"])},
        {
            "$set": {
                "detail_etag": "\"lot-etag-1\"",
                "last_checked_at": datetime(2026, 3, 20, 16, 59, 15, tzinfo=timezone.utc),
                "auction_reminder_sent_minutes": [60, 15],
            }
        },
    )
    monitoring = MonitoringService(
        database,
        provider_factory=lambda: EtagAwareProvider(None, not_modified=True, etag="\"lot-etag-2\""),
        notification_service=notification_service,
    )

    result = monitoring.poll_due_lots(now=datetime(2026, 3, 20, 17, 0, 15, tzinfo=timezone.utc))

    assert result["processed"] == 1
    assert result["reminded"] == 1
    assert notification_service.reminder_events[0]["reminder_offset_minutes"] == 0
    tracked_lot = database["tracked_lots"].find_one({"_id": ObjectId(created["tracked_lot"]["id"])})
    assert tracked_lot["auction_reminder_sent_minutes"] == [60, 15, 0]
