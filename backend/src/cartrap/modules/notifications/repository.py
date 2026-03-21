"""Mongo-backed repository for push subscriptions."""

from __future__ import annotations

from typing import Optional

from bson import ObjectId
from pymongo.errors import DuplicateKeyError
from pymongo.collection import Collection
from pymongo.database import Database

from cartrap.modules.notifications.models import PUSH_DELIVERY_RECEIPTS_COLLECTION, PUSH_SUBSCRIPTIONS_COLLECTION


class NotificationRepository:
    def __init__(self, database: Database) -> None:
        self.push_subscriptions: Collection = database[PUSH_SUBSCRIPTIONS_COLLECTION]
        self.push_delivery_receipts: Collection = database[PUSH_DELIVERY_RECEIPTS_COLLECTION]

    def ensure_indexes(self) -> None:
        self.push_subscriptions.create_index([("owner_user_id", 1), ("endpoint", 1)], unique=True)
        self.push_subscriptions.create_index("owner_user_id")
        self.push_delivery_receipts.create_index("dedupe_key", unique=True)
        self.push_delivery_receipts.create_index([("owner_user_id", 1), ("created_at", -1)])

    def upsert_subscription(self, owner_user_id: str, payload: dict) -> dict:
        document = dict(payload)
        self.push_subscriptions.update_one(
            {"owner_user_id": owner_user_id, "endpoint": document["endpoint"]},
            {"$set": document, "$setOnInsert": {"owner_user_id": owner_user_id, "created_at": document["updated_at"]}},
            upsert=True,
        )
        return self.push_subscriptions.find_one({"owner_user_id": owner_user_id, "endpoint": document["endpoint"]})

    def list_subscriptions_for_owner(self, owner_user_id: str) -> list[dict]:
        return list(self.push_subscriptions.find({"owner_user_id": owner_user_id}).sort("created_at", -1))

    def delete_subscription(self, owner_user_id: str, endpoint: str) -> int:
        result = self.push_subscriptions.delete_one({"owner_user_id": owner_user_id, "endpoint": endpoint})
        return result.deleted_count

    def delete_subscription_by_id(self, subscription_id: str) -> None:
        self.push_subscriptions.delete_one({"_id": ObjectId(subscription_id)})

    def get_subscriptions_for_owner(self, owner_user_id: str) -> list[dict]:
        return list(self.push_subscriptions.find({"owner_user_id": owner_user_id}))

    def find_subscription_by_endpoint(self, owner_user_id: str, endpoint: str) -> Optional[dict]:
        return self.push_subscriptions.find_one({"owner_user_id": owner_user_id, "endpoint": endpoint})

    def has_delivery_receipt(self, dedupe_key: str) -> bool:
        return self.push_delivery_receipts.find_one({"dedupe_key": dedupe_key}) is not None

    def create_delivery_receipt(self, dedupe_key: str, payload: dict) -> bool:
        try:
            self.push_delivery_receipts.insert_one({"dedupe_key": dedupe_key, **payload})
        except DuplicateKeyError:
            return False
        return True
