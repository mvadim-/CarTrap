"""Persistence helpers for shared backend system status."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pymongo import ReturnDocument
from pymongo.database import Database


LIVE_SYNC_STATUS_ID = "live_sync"


class SystemStatusRepository:
    def __init__(self, database: Database) -> None:
        self._collection = database["system_status"]

    def get_live_sync_status(self) -> Optional[dict]:
        return self._collection.find_one({"_id": LIVE_SYNC_STATUS_ID})

    def update_live_sync_status(self, payload: dict) -> dict:
        document = self._collection.find_one_and_update(
            {"_id": LIVE_SYNC_STATUS_ID},
            {"$set": {"_id": LIVE_SYNC_STATUS_ID, **payload}},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        if document is None:
            raise RuntimeError("Failed to persist live sync status.")
        return document

    def set_live_sync_available(self, checked_at: datetime, source: str) -> dict:
        payload = {
            "availability": "available",
            "last_success_at": checked_at,
            "last_success_source": source,
            "updated_at": checked_at,
        }
        return self.update_live_sync_status(payload)

    def set_live_sync_degraded(self, checked_at: datetime, source: str, error_message: str) -> dict:
        payload = {
            "availability": "degraded",
            "last_failure_at": checked_at,
            "last_failure_source": source,
            "last_error_message": error_message,
            "updated_at": checked_at,
        }
        return self.update_live_sync_status(payload)
