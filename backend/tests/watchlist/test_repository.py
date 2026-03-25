from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys

import mongomock


ROOT = Path(__file__).resolve().parents[2] / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from cartrap.modules.watchlist.repository import WatchlistRepository


def _build_legacy_tracked_lot(*, owner_user_id: str, lot_number: str) -> dict:
    now = datetime(2026, 3, 25, 16, 0, tzinfo=timezone.utc)
    return {
        "owner_user_id": owner_user_id,
        "lot_number": lot_number,
        "url": f"https://www.copart.com/lot/{lot_number}",
        "title": f"Lot {lot_number}",
        "status": "upcoming",
        "raw_status": "Upcoming",
        "currency": "USD",
        "last_checked_at": now,
        "active": True,
        "created_at": now,
        "updated_at": now,
        "lot_key": None,
    }


def test_ensure_indexes_backfills_legacy_identity_before_unique_index_creation() -> None:
    database = mongomock.MongoClient(tz_aware=True)["cartrap_test"]
    repository = WatchlistRepository(database)
    repository.tracked_lots.insert_many(
        [
            _build_legacy_tracked_lot(owner_user_id="user-1", lot_number="12345678"),
            _build_legacy_tracked_lot(owner_user_id="user-1", lot_number="87654321"),
        ]
    )

    repository.ensure_indexes()

    documents = list(repository.tracked_lots.find({}, {"_id": 0, "provider": 1, "provider_lot_id": 1, "lot_key": 1}))
    assert documents == [
        {"provider": "copart", "provider_lot_id": "12345678", "lot_key": "copart:12345678"},
        {"provider": "copart", "provider_lot_id": "87654321", "lot_key": "copart:87654321"},
    ]


def test_ensure_indexes_tolerates_unbackfillable_legacy_null_lot_keys() -> None:
    database = mongomock.MongoClient(tz_aware=True)["cartrap_test"]
    repository = WatchlistRepository(database)
    now = datetime(2026, 3, 25, 16, 5, tzinfo=timezone.utc)
    repository.tracked_lots.insert_many(
        [
            {
                "owner_user_id": "user-1",
                "title": "Broken legacy row 1",
                "status": "upcoming",
                "raw_status": "Upcoming",
                "currency": "USD",
                "last_checked_at": now,
                "active": True,
                "created_at": now,
                "updated_at": now,
                "lot_key": None,
            },
            {
                "owner_user_id": "user-1",
                "title": "Broken legacy row 2",
                "status": "upcoming",
                "raw_status": "Upcoming",
                "currency": "USD",
                "last_checked_at": now,
                "active": True,
                "created_at": now,
                "updated_at": now,
                "lot_key": None,
            },
        ]
    )

    repository.ensure_indexes()

    assert repository.tracked_lots.count_documents({"owner_user_id": "user-1"}) == 2
