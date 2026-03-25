"""Mongo-backed persistence for watchlist data."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from bson import ObjectId
from pymongo.collection import Collection
from pymongo.database import Database

from cartrap.modules.watchlist.models import LOT_SNAPSHOTS_COLLECTION, TRACKED_LOTS_COLLECTION


class WatchlistRepository:
    def __init__(self, database: Database) -> None:
        self.tracked_lots: Collection = database[TRACKED_LOTS_COLLECTION]
        self.lot_snapshots: Collection = database[LOT_SNAPSHOTS_COLLECTION]

    def ensure_indexes(self) -> None:
        self.tracked_lots.create_index([("owner_user_id", 1), ("lot_key", 1)], unique=True)
        self.tracked_lots.create_index("owner_user_id")
        self.lot_snapshots.create_index([("tracked_lot_id", 1), ("detected_at", -1)])

    def create_tracked_lot(self, payload: dict) -> dict:
        document = dict(payload)
        result = self.tracked_lots.insert_one(document)
        document["_id"] = result.inserted_id
        return document

    def create_snapshot(self, payload: dict) -> dict:
        document = dict(payload)
        result = self.lot_snapshots.insert_one(document)
        document["_id"] = result.inserted_id
        return document

    def find_tracked_lot_by_owner_and_lot_key(self, owner_user_id: str, lot_key: str) -> Optional[dict]:
        return self.tracked_lots.find_one({"owner_user_id": owner_user_id, "lot_key": lot_key})

    def list_tracked_lots_for_owner(self, owner_user_id: str) -> list[dict]:
        return list(self.tracked_lots.find({"owner_user_id": owner_user_id}))

    def list_active_tracked_lots(self) -> list[dict]:
        return list(self.tracked_lots.find({"active": True}).sort("last_checked_at", 1))

    def find_tracked_lot_by_id_for_owner(self, tracked_lot_id: str, owner_user_id: str) -> Optional[dict]:
        return self.tracked_lots.find_one({"_id": ObjectId(tracked_lot_id), "owner_user_id": owner_user_id})

    def delete_tracked_lot(self, tracked_lot_id: str) -> None:
        tracked_object_id = ObjectId(tracked_lot_id)
        self.tracked_lots.delete_one({"_id": tracked_object_id})
        self.lot_snapshots.delete_many({"tracked_lot_id": tracked_lot_id})

    def list_snapshots_for_tracked_lot(self, tracked_lot_id: str) -> list[dict]:
        return list(self.lot_snapshots.find({"tracked_lot_id": tracked_lot_id}).sort("detected_at", -1))

    def get_latest_snapshot_for_tracked_lot(self, tracked_lot_id: str) -> Optional[dict]:
        return self.lot_snapshots.find_one({"tracked_lot_id": tracked_lot_id}, sort=[("detected_at", -1)])

    def count_snapshots_for_tracked_lot(self, tracked_lot_id: str) -> int:
        return self.lot_snapshots.count_documents({"tracked_lot_id": tracked_lot_id})

    def update_tracked_lot_state(self, tracked_lot_id: str, payload: dict, updated_at: datetime) -> None:
        self.tracked_lots.update_one(
            {"_id": ObjectId(tracked_lot_id)},
            {"$set": {**payload, "updated_at": updated_at}},
        )

    def request_legacy_backfill(self, tracked_lot_id: str, requested_at: datetime) -> None:
        self.tracked_lots.update_one(
            {"_id": ObjectId(tracked_lot_id)},
            {"$set": {"repair_requested_at": requested_at, "updated_at": requested_at}},
        )

    def clear_unseen_updates(self, tracked_lot_ids: list[str]) -> None:
        if not tracked_lot_ids:
            return
        self.tracked_lots.update_many(
            {"_id": {"$in": [ObjectId(tracked_lot_id) for tracked_lot_id in tracked_lot_ids]}},
            {"$set": {"has_unseen_update": False, "latest_change_at": None, "latest_changes": {}}},
        )
