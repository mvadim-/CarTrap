"""Mongo persistence for admin-managed runtime setting overrides."""

from __future__ import annotations

from datetime import datetime

from pymongo.collection import Collection
from pymongo.database import Database


RUNTIME_SETTINGS_COLLECTION = "admin_runtime_settings"


class RuntimeSettingsRepository:
    def __init__(self, database: Database) -> None:
        self._collection: Collection = database[RUNTIME_SETTINGS_COLLECTION]

    def ensure_indexes(self) -> None:
        self._collection.create_index("key", unique=True)
        self._collection.create_index("updated_at")

    def list_overrides(self) -> list[dict]:
        return list(self._collection.find().sort("key", 1))

    def find_override(self, key: str) -> dict | None:
        return self._collection.find_one({"key": key})

    def upsert_override(
        self,
        *,
        key: str,
        value: int | list[int],
        value_type: str,
        updated_by: str,
        updated_at: datetime,
    ) -> dict:
        self._collection.update_one(
            {"key": key},
            {
                "$set": {
                    "key": key,
                    "value": value,
                    "value_type": value_type,
                    "updated_by": updated_by,
                    "updated_at": updated_at,
                },
            },
            upsert=True,
        )
        return self.find_override(key) or {}

    def delete_override(self, key: str) -> None:
        self._collection.delete_one({"key": key})

    def delete_overrides(self, keys: list[str]) -> None:
        if not keys:
            return
        self._collection.delete_many({"key": {"$in": keys}})
