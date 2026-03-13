from __future__ import annotations

from pathlib import Path
import sys

from datetime import datetime, timezone

from bson import ObjectId
import mongomock


ROOT = Path(__file__).resolve().parents[2] / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from cartrap.modules.copart_provider.models import CopartLotSnapshot
from cartrap.modules.watchlist.service import WatchlistService


class FakeProvider:
    def __init__(self, snapshot: CopartLotSnapshot) -> None:
        self._snapshot = snapshot

    def fetch_lot(self, url: str) -> CopartLotSnapshot:
        assert url == str(self._snapshot.url)
        return self._snapshot

    def close(self) -> None:
        return None


def test_initial_snapshot_is_stored_with_tracked_lot_state() -> None:
    database = mongomock.MongoClient(tz_aware=True)["cartrap_test"]
    snapshot = CopartLotSnapshot(
        lot_number="12345678",
        title="2020 TOYOTA CAMRY SE",
        url="https://www.copart.com/lot/12345678",
        thumbnail_url="https://img.copart.com/12345678-detail.jpg",
        image_urls=[
            "https://img.copart.com/12345678-detail.jpg",
            "https://img.copart.com/12345678-detail-2.jpg",
        ],
        odometer="12,345 ACTUAL",
        primary_damage="FRONT END",
        estimated_retail_value=36500.0,
        has_key=True,
        drivetrain="AWD",
        highlights=["Run and Drive"],
        vin="1FA6P8TH0J5100001",
        status="on_approval",
        raw_status="On Approval",
        sale_date=datetime(2026, 3, 20, 17, 0, tzinfo=timezone.utc),
        current_bid=4200.0,
        buy_now_price=6500.0,
        currency="USD",
    )
    service = WatchlistService(database, provider_factory=lambda: FakeProvider(snapshot))

    result = service.add_tracked_lot({"id": "user-1"}, "https://www.copart.com/lot/12345678")

    tracked_lot = database["tracked_lots"].find_one({"_id": ObjectId(result["tracked_lot"]["id"])})
    snapshots = list(database["lot_snapshots"].find({"tracked_lot_id": result["tracked_lot"]["id"]}))

    assert tracked_lot is not None
    assert tracked_lot["lot_number"] == "12345678"
    assert tracked_lot["thumbnail_url"] == "https://img.copart.com/12345678-detail.jpg"
    assert tracked_lot["image_urls"] == [
        "https://img.copart.com/12345678-detail.jpg",
        "https://img.copart.com/12345678-detail-2.jpg",
    ]
    assert tracked_lot["odometer"] == "12,345 ACTUAL"
    assert tracked_lot["primary_damage"] == "FRONT END"
    assert tracked_lot["estimated_retail_value"] == 36500.0
    assert tracked_lot["has_key"] is True
    assert tracked_lot["drivetrain"] == "AWD"
    assert tracked_lot["highlights"] == ["Run and Drive"]
    assert tracked_lot["vin"] == "1FA6P8TH0J5100001"
    assert tracked_lot["status"] == "on_approval"
    assert len(snapshots) == 1
    assert snapshots[0]["current_bid"] == 4200.0
    assert snapshots[0]["tracked_lot_id"] == result["tracked_lot"]["id"]
