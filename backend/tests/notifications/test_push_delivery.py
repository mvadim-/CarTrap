from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys

import mongomock
import pytest


ROOT = Path(__file__).resolve().parents[2] / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from cartrap.modules.copart_provider.models import CopartLotSnapshot
from cartrap.modules.monitoring.service import MonitoringService
from cartrap.modules.notifications.service import NotificationService, PushDeliveryError, WebPushSender
from cartrap.modules.watchlist.service import WatchlistService


class FakeProvider:
    def __init__(self, snapshot: CopartLotSnapshot) -> None:
        self._snapshot = snapshot

    def fetch_lot(self, url: str) -> CopartLotSnapshot:
        return self._snapshot

    def close(self) -> None:
        return None


class FakeSender:
    def __init__(self, fail_endpoint: str | None = None, *, unrecoverable: bool = True) -> None:
        self.fail_endpoint = fail_endpoint
        self.unrecoverable = unrecoverable
        self.sent: list[tuple[str, dict]] = []

    def send(self, subscription: dict, payload: dict) -> None:
        if subscription["endpoint"] == self.fail_endpoint:
            raise PushDeliveryError("push delivery failed", unrecoverable=self.unrecoverable)
        self.sent.append((subscription["endpoint"], payload))


def test_notification_delivery_sends_to_active_subscriptions() -> None:
    database = mongomock.MongoClient(tz_aware=True)["cartrap_test"]
    sender = FakeSender()
    notification_service = NotificationService(database, sender=sender)
    notification_service.upsert_subscription(
        {"id": "user-1"},
        {
            "subscription": {
                "endpoint": "https://push.example.test/subscriptions/1",
                "expirationTime": None,
                "keys": {"p256dh": "abc", "auth": "def"},
            }
        },
    )
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
    WatchlistService(database, provider_factory=lambda: FakeProvider(initial_snapshot)).add_tracked_lot(
        {"id": "user-1"},
        "https://www.copart.com/lot/12345678",
    )

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
    monitoring_service = MonitoringService(
        database,
        provider_factory=lambda: FakeProvider(changed_snapshot),
        notification_service=notification_service,
    )

    result = monitoring_service.poll_due_lots(now=datetime(2026, 3, 20, 16, 30, tzinfo=timezone.utc))

    assert result["updated"] == 1
    assert result["reminded"] == 1
    assert len(sender.sent) == 2
    assert sender.sent[0][1]["tracked_lot_id"] == result["events"][0]["tracked_lot_id"]
    assert sender.sent[0][1]["title"] == "2020 TOYOTA CAMRY SE (12345678)"
    assert sender.sent[0][1]["body"] == "Status: Upcoming -> Live; Bid: 1,000 -> 1,800 USD"
    assert sender.sent[1][1]["body"] == "Auction starts in 1 hour."


def test_failed_delivery_removes_invalid_subscription() -> None:
    database = mongomock.MongoClient(tz_aware=True)["cartrap_test"]
    sender = FakeSender(fail_endpoint="https://push.example.test/subscriptions/bad")
    notification_service = NotificationService(database, sender=sender)
    notification_service.upsert_subscription(
        {"id": "user-2"},
        {
            "subscription": {
                "endpoint": "https://push.example.test/subscriptions/bad",
                "expirationTime": None,
                "keys": {"p256dh": "bad", "auth": "bad"},
            }
        },
    )

    result = notification_service.send_lot_change_notification(
        {
            "tracked_lot_id": "tracked-1",
            "owner_user_id": "user-2",
            "lot_number": "87654321",
            "title": "2018 HONDA CIVIC EX",
            "currency": "USD",
            "changes": {"status": {"before": "upcoming", "after": "live"}},
        }
    )

    assert result["delivered"] == 0
    assert result["failed"] == 1
    assert result["removed"] == 1
    assert database["push_subscriptions"].count_documents({}) == 0


def test_transient_delivery_failure_keeps_subscription() -> None:
    database = mongomock.MongoClient(tz_aware=True)["cartrap_test"]
    sender = FakeSender(
        fail_endpoint="https://push.example.test/subscriptions/transient",
        unrecoverable=False,
    )
    notification_service = NotificationService(database, sender=sender)
    notification_service.upsert_subscription(
        {"id": "user-3"},
        {
            "subscription": {
                "endpoint": "https://push.example.test/subscriptions/transient",
                "expirationTime": None,
                "keys": {"p256dh": "bad", "auth": "bad"},
            }
        },
    )

    result = notification_service.send_lot_change_notification(
        {
            "tracked_lot_id": "tracked-2",
            "owner_user_id": "user-3",
            "lot_number": "12344321",
            "title": "2020 TOYOTA CAMRY SE",
            "currency": "USD",
            "changes": {"current_bid": {"before": 1000, "after": 1200}},
        }
    )

    assert result["delivered"] == 0
    assert result["failed"] == 1
    assert result["removed"] == 0
    assert database["push_subscriptions"].count_documents({}) == 1


def test_auction_reminder_notification_formats_expected_copy() -> None:
    database = mongomock.MongoClient(tz_aware=True)["cartrap_test"]
    sender = FakeSender()
    notification_service = NotificationService(database, sender=sender)
    notification_service.upsert_subscription(
        {"id": "user-4"},
        {
            "subscription": {
                "endpoint": "https://push.example.test/subscriptions/4",
                "expirationTime": None,
                "keys": {"p256dh": "abc", "auth": "def"},
            }
        },
    )

    result = notification_service.send_auction_reminder_notification(
        {
            "tracked_lot_id": "tracked-4",
            "owner_user_id": "user-4",
            "lot_number": "12344321",
            "title": "2020 TOYOTA CAMRY SE",
            "sale_date": datetime(2026, 3, 20, 17, 0, tzinfo=timezone.utc),
            "reminder_offset_minutes": 15,
        }
    )

    assert result["delivered"] == 1
    assert sender.sent[0][1]["title"] == "2020 TOYOTA CAMRY SE (12344321)"
    assert sender.sent[0][1]["body"] == "Auction starts in 15 min."


def test_web_push_sender_serializes_payload_and_vapid_claims(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    def fake_webpush(**kwargs):
        captured.update(kwargs)
        return None

    monkeypatch.setattr("cartrap.modules.notifications.service.webpush", fake_webpush)

    sender = WebPushSender(
        vapid_private_key="private-key",
        vapid_subject="mailto:admin@example.com",
    )
    sender.send(
        {
            "endpoint": "https://push.example.test/subscriptions/real",
            "keys": {"p256dh": "abc", "auth": "def"},
        },
        {"title": "Lot updated", "body": "status"},
    )

    assert captured["subscription_info"] == {
        "endpoint": "https://push.example.test/subscriptions/real",
        "keys": {"p256dh": "abc", "auth": "def"},
    }
    assert captured["vapid_private_key"] == "private-key"
    assert captured["vapid_claims"] == {"sub": "mailto:admin@example.com"}
    assert "Lot updated" in captured["data"]
