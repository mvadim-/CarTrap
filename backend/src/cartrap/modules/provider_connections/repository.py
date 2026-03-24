"""Mongo persistence for provider connections."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import ReturnDocument
from pymongo.collection import Collection
from pymongo.database import Database

from cartrap.modules.provider_connections.models import PROVIDER_CONNECTIONS_COLLECTION


class ProviderConnectionRepository:
    def __init__(self, database: Database) -> None:
        self.provider_connections: Collection = database[PROVIDER_CONNECTIONS_COLLECTION]

    def ensure_indexes(self) -> None:
        self.provider_connections.create_index([("owner_user_id", 1), ("provider", 1)], unique=True)
        self.provider_connections.create_index([("owner_user_id", 1), ("updated_at", -1)])
        self.provider_connections.create_index([("provider", 1), ("status", 1)])

    def list_for_owner(self, owner_user_id: str) -> list[dict]:
        return list(self.provider_connections.find({"owner_user_id": owner_user_id}).sort("updated_at", -1))

    def find_by_user_and_provider(self, owner_user_id: str, provider: str) -> Optional[dict]:
        return self.provider_connections.find_one({"owner_user_id": owner_user_id, "provider": provider})

    def find_by_id_for_owner(self, connection_id: str, owner_user_id: str) -> Optional[dict]:
        try:
            object_id = ObjectId(connection_id)
        except (InvalidId, TypeError):
            return None
        return self.provider_connections.find_one({"_id": object_id, "owner_user_id": owner_user_id})

    def upsert_connection(self, owner_user_id: str, provider: str, payload: dict) -> dict:
        document = self.provider_connections.find_one_and_update(
            {"owner_user_id": owner_user_id, "provider": provider},
            {
                "$set": dict(payload),
                "$setOnInsert": {
                    "owner_user_id": owner_user_id,
                    "provider": provider,
                    "created_at": payload["updated_at"],
                },
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        if document is None:
            raise RuntimeError("Failed to upsert provider connection.")
        return document

    def update_connection(self, connection_id: str, payload: dict) -> Optional[dict]:
        return self.provider_connections.find_one_and_update(
            {"_id": ObjectId(connection_id)},
            {"$set": dict(payload)},
            return_document=ReturnDocument.AFTER,
        )

    def disconnect_connection(self, connection_id: str, *, disconnected_at: datetime, updated_at: datetime) -> Optional[dict]:
        return self.provider_connections.find_one_and_update(
            {"_id": ObjectId(connection_id)},
            {
                "$set": {
                    "status": "disconnected",
                    "disconnected_at": disconnected_at,
                    "updated_at": updated_at,
                    "encrypted_session_bundle": None,
                    "encrypted_session_bundle_key_version": None,
                    "bundle_captured_at": None,
                    "bundle_expires_at": None,
                    "bundle_version": 1,
                    "last_error": None,
                }
            },
            return_document=ReturnDocument.AFTER,
        )

    def compare_and_swap_bundle(
        self,
        connection_id: str,
        *,
        expected_bundle_version: int,
        encrypted_session_bundle: str,
        encrypted_session_bundle_key_version: str,
        bundle_captured_at: datetime | None,
        bundle_expires_at: datetime | None,
        updated_at: datetime,
        status: str,
        last_verified_at: datetime | None,
        last_used_at: datetime | None,
    ) -> Optional[dict]:
        return self.provider_connections.find_one_and_update(
            {
                "_id": ObjectId(connection_id),
                "bundle_version": expected_bundle_version,
            },
            {
                "$set": {
                    "encrypted_session_bundle": encrypted_session_bundle,
                    "encrypted_session_bundle_key_version": encrypted_session_bundle_key_version,
                    "bundle_captured_at": bundle_captured_at,
                    "bundle_expires_at": bundle_expires_at,
                    "updated_at": updated_at,
                    "status": status,
                    "last_verified_at": last_verified_at,
                    "last_used_at": last_used_at,
                    "last_error": None,
                },
                "$inc": {"bundle_version": 1},
            },
            return_document=ReturnDocument.AFTER,
        )
