"""Mongo-backed persistence for watchlist data."""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Optional

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from cartrap.modules.auction_domain.models import backfill_lot_identity
from cartrap.modules.watchlist.models import LOT_SNAPSHOTS_COLLECTION, TRACKED_LOTS_COLLECTION


logger = logging.getLogger(__name__)


class WatchlistRepository:
    def __init__(self, database: Database) -> None:
        self.tracked_lots: Collection = database[TRACKED_LOTS_COLLECTION]
        self.lot_snapshots: Collection = database[LOT_SNAPSHOTS_COLLECTION]

    def ensure_indexes(self) -> None:
        self._backfill_legacy_lot_identity()
        try:
            self.tracked_lots.create_index(
                [("owner_user_id", 1), ("lot_key", 1)],
                unique=True,
                partialFilterExpression={"lot_key": {"$type": "string"}},
            )
        except DuplicateKeyError:
            logger.exception(
                "Failed to create unique tracked_lots index after lot identity backfill; "
                "duplicate owner_user_id + lot_key records remain in Mongo."
            )
        self.tracked_lots.create_index("owner_user_id")
        self.lot_snapshots.create_index([("tracked_lot_id", 1), ("detected_at", -1)])

    def _backfill_legacy_lot_identity(self) -> None:
        legacy_documents = self.tracked_lots.find(
            {
                "$or": [
                    {"provider": {"$exists": False}},
                    {"provider_lot_id": {"$exists": False}},
                    {"provider_lot_id": None},
                    {"auction_label": {"$exists": False}},
                    {"lot_key": {"$exists": False}},
                    {"lot_key": None},
                ]
            }
        )
        for document in legacy_documents:
            try:
                backfilled = backfill_lot_identity(document)
            except ValueError:
                logger.warning(
                    "Skipping tracked_lots identity backfill for document %s because provider_lot_id/lot_number is missing.",
                    document.get("_id"),
                )
                continue
            self.tracked_lots.update_one(
                {"_id": document["_id"]},
                {
                    "$set": {
                        "provider": backfilled["provider"],
                        "auction_label": backfilled["auction_label"],
                        "provider_lot_id": backfilled["provider_lot_id"],
                        "lot_key": backfilled["lot_key"],
                    }
                },
            )

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

    def list_all_tracked_lots(self) -> list[dict]:
        return list(self.tracked_lots.find())

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

    def purge_snapshots_for_tracked_lot(self, tracked_lot_id: str) -> int:
        result = self.lot_snapshots.delete_many({"tracked_lot_id": tracked_lot_id})
        return result.deleted_count

    def purge_snapshots_for_owner(self, owner_user_id: str) -> int:
        tracked_lot_ids = [str(document["_id"]) for document in self.list_tracked_lots_for_owner(owner_user_id)]
        if not tracked_lot_ids:
            return 0
        result = self.lot_snapshots.delete_many({"tracked_lot_id": {"$in": tracked_lot_ids}})
        return result.deleted_count

    def delete_tracked_lots_for_owner(self, owner_user_id: str) -> dict[str, int]:
        tracked_lots = self.list_tracked_lots_for_owner(owner_user_id)
        tracked_lot_ids = [str(document["_id"]) for document in tracked_lots]
        deleted_snapshots = 0
        if tracked_lot_ids:
            deleted_snapshots = self.lot_snapshots.delete_many({"tracked_lot_id": {"$in": tracked_lot_ids}}).deleted_count
        deleted_tracked_lots = self.tracked_lots.delete_many({"owner_user_id": owner_user_id}).deleted_count
        return {
            "tracked_lots": deleted_tracked_lots,
            "lot_snapshots": deleted_snapshots,
        }

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

    def acknowledge_tracked_lot_update(self, tracked_lot_id: str, acknowledged_at: datetime) -> Optional[dict]:
        return self.tracked_lots.find_one_and_update(
            {"_id": ObjectId(tracked_lot_id)},
            {"$set": {"has_unseen_update": False, "updated_at": acknowledged_at}},
            return_document=ReturnDocument.AFTER,
        )
