"""Mongo-backed persistence for search catalog and saved-search data."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from bson import ObjectId
from bson.errors import InvalidId
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo import ReturnDocument

from cartrap.modules.auction_domain.models import build_lot_key
from cartrap.modules.search.models import (
    SAVED_SEARCHES_COLLECTION,
    SAVED_SEARCH_RESULTS_CACHE_COLLECTION,
    SEARCH_CATALOG_COLLECTION,
    SEARCH_CATALOG_DOCUMENT_ID,
)


class SearchCatalogRepository:
    def __init__(self, database: Database) -> None:
        self.catalog: Collection = database[SEARCH_CATALOG_COLLECTION]

    def ensure_indexes(self) -> None:
        self.catalog.create_index("generated_at")

    def get_catalog(self) -> Optional[dict]:
        return self.catalog.find_one({"_id": SEARCH_CATALOG_DOCUMENT_ID})

    def replace_catalog(self, payload: dict, updated_at: datetime) -> dict:
        document = dict(payload)
        document["_id"] = SEARCH_CATALOG_DOCUMENT_ID
        document["updated_at"] = updated_at
        self.catalog.replace_one({"_id": SEARCH_CATALOG_DOCUMENT_ID}, document, upsert=True)
        return document


class SavedSearchRepository:
    def __init__(self, database: Database) -> None:
        self.saved_searches: Collection = database[SAVED_SEARCHES_COLLECTION]
        self.saved_search_results_cache: Collection = database[SAVED_SEARCH_RESULTS_CACHE_COLLECTION]

    def ensure_indexes(self) -> None:
        self.saved_searches.create_index([("owner_user_id", 1), ("criteria_key", 1)], unique=True)
        self.saved_searches.create_index([("owner_user_id", 1), ("created_at", -1)])
        self.saved_searches.create_index("last_checked_at")
        self.saved_search_results_cache.create_index("saved_search_id", unique=True)
        self.saved_search_results_cache.create_index([("owner_user_id", 1), ("last_synced_at", -1)])

    def create_saved_search(self, payload: dict) -> dict:
        document = dict(payload)
        result = self.saved_searches.insert_one(document)
        document["_id"] = result.inserted_id
        return document

    def list_saved_searches_for_owner(self, owner_user_id: str) -> list[dict]:
        return list(self.saved_searches.find({"owner_user_id": owner_user_id}).sort("created_at", -1))

    def list_all_saved_searches(self) -> list[dict]:
        return list(self.saved_searches.find().sort("created_at", -1))

    def find_saved_search_by_owner_and_key(self, owner_user_id: str, criteria_key: str) -> Optional[dict]:
        return self.saved_searches.find_one({"owner_user_id": owner_user_id, "criteria_key": criteria_key})

    def find_saved_search_by_id_for_owner(self, saved_search_id: str, owner_user_id: str) -> Optional[dict]:
        try:
            object_id = ObjectId(saved_search_id)
        except (InvalidId, TypeError):
            return None
        return self.saved_searches.find_one({"_id": object_id, "owner_user_id": owner_user_id})

    def delete_saved_search(self, saved_search_id: str) -> None:
        object_id = ObjectId(saved_search_id)
        self.saved_searches.delete_one({"_id": object_id})
        self.saved_search_results_cache.delete_one({"saved_search_id": object_id})

    def list_due_saved_searches(self, due_before: datetime) -> list[dict]:
        return list(
            self.saved_searches.find(
                {
                    "$or": [
                        {"last_checked_at": {"$exists": False}},
                        {"last_checked_at": None},
                        {"last_checked_at": {"$lte": due_before}},
                    ]
                }
            ).sort("created_at", 1)
        )

    def update_saved_search_poll_state(
        self,
        saved_search_id: str,
        *,
        result_count: int,
        last_checked_at: datetime,
        updated_at: datetime,
        search_etag: Optional[str] = None,
    ) -> dict:
        object_id = ObjectId(saved_search_id)
        self.saved_searches.update_one(
            {"_id": object_id},
            {
                "$set": {
                    "result_count": result_count,
                    "last_checked_at": last_checked_at,
                    "search_etag": search_etag,
                    "updated_at": updated_at,
                }
            },
        )
        return self.saved_searches.find_one({"_id": object_id})

    def update_saved_search_refresh_state(self, saved_search_id: str, payload: dict) -> Optional[dict]:
        object_id = ObjectId(saved_search_id)
        self.saved_searches.update_one({"_id": object_id}, {"$set": dict(payload)})
        return self.saved_searches.find_one({"_id": object_id})

    def find_saved_search_cache_by_id_for_owner(self, saved_search_id: str, owner_user_id: str) -> Optional[dict]:
        try:
            object_id = ObjectId(saved_search_id)
        except (InvalidId, TypeError):
            return None
        return self.saved_search_results_cache.find_one({"saved_search_id": object_id, "owner_user_id": owner_user_id})

    def list_saved_search_caches_for_owner(self, owner_user_id: str, saved_search_ids: list[str] | None = None) -> list[dict]:
        query: dict = {"owner_user_id": owner_user_id}
        if saved_search_ids is not None:
            object_ids = []
            for saved_search_id in saved_search_ids:
                try:
                    object_ids.append(ObjectId(saved_search_id))
                except (InvalidId, TypeError):
                    continue
            if not object_ids:
                return []
            query["saved_search_id"] = {"$in": object_ids}
        return list(self.saved_search_results_cache.find(query))

    def list_all_saved_search_caches(self) -> list[dict]:
        return list(self.saved_search_results_cache.find())

    def upsert_saved_search_cache(
        self,
        saved_search_id: str,
        owner_user_id: str,
        *,
        results: list[dict],
        result_count: int,
        new_lot_keys: Optional[list[str]] = None,
        new_lot_numbers: Optional[list[str]] = None,
        last_synced_at: datetime,
        seen_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> dict:
        object_id = ObjectId(saved_search_id)
        write_time = updated_at or last_synced_at
        normalized_new_lot_keys = self._normalize_new_lot_keys(
            results,
            new_lot_keys=new_lot_keys,
            new_lot_numbers=new_lot_numbers,
        )
        normalized_new_lot_numbers = [
            item.get("lot_number")
            for item in results
            if (
                item.get("lot_key")
                or build_lot_key(item.get("provider"), item.get("provider_lot_id"), item.get("lot_number"))
            )
            in set(normalized_new_lot_keys)
            and item.get("lot_number")
        ]
        return self.saved_search_results_cache.find_one_and_update(
            {"saved_search_id": object_id, "owner_user_id": owner_user_id},
            {
                "$set": {
                    "owner_user_id": owner_user_id,
                    "results": list(results),
                    "result_count": result_count,
                    "new_lot_keys": list(dict.fromkeys(normalized_new_lot_keys)),
                    "new_lot_numbers": list(dict.fromkeys(normalized_new_lot_numbers)),
                    "last_synced_at": last_synced_at,
                    "seen_at": seen_at,
                    "updated_at": write_time,
                },
                "$setOnInsert": {
                    "saved_search_id": object_id,
                    "created_at": write_time,
                },
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )

    @staticmethod
    def _normalize_new_lot_keys(
        results: list[dict],
        *,
        new_lot_keys: Optional[list[str]],
        new_lot_numbers: Optional[list[str]],
    ) -> list[str]:
        if new_lot_keys:
            return [str(item) for item in new_lot_keys if item]
        if not new_lot_numbers:
            return []
        requested_numbers = {str(item) for item in new_lot_numbers if item}
        normalized: list[str] = []
        for item in results:
            lot_number = item.get("lot_number")
            if lot_number not in requested_numbers:
                continue
            normalized.append(
                item.get("lot_key")
                or build_lot_key(item.get("provider"), item.get("provider_lot_id"), lot_number)
            )
        return normalized

    def mark_saved_search_cache_viewed(
        self,
        saved_search_id: str,
        owner_user_id: str,
        *,
        seen_at: datetime,
        updated_at: datetime | None = None,
    ) -> Optional[dict]:
        try:
            object_id = ObjectId(saved_search_id)
        except (InvalidId, TypeError):
            return None
        return self.saved_search_results_cache.find_one_and_update(
            {"saved_search_id": object_id, "owner_user_id": owner_user_id},
            {
                "$set": {
                    "seen_at": seen_at,
                    "updated_at": updated_at or seen_at,
                    "new_lot_keys": [],
                    "new_lot_numbers": [],
                }
            },
            return_document=ReturnDocument.BEFORE,
        )

    def delete_saved_searches_for_owner(self, owner_user_id: str) -> dict[str, int]:
        saved_searches = self.list_saved_searches_for_owner(owner_user_id)
        saved_search_object_ids = [document["_id"] for document in saved_searches]
        deleted_saved_searches = self.saved_searches.delete_many({"owner_user_id": owner_user_id}).deleted_count
        cache_query: dict = {"owner_user_id": owner_user_id}
        if saved_search_object_ids:
            cache_query["saved_search_id"] = {"$in": saved_search_object_ids}
        deleted_caches = self.saved_search_results_cache.delete_many(cache_query).deleted_count
        return {
            "saved_searches": deleted_saved_searches,
            "saved_search_caches": deleted_caches,
        }
