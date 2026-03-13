"""Mongo-backed persistence for search catalog and saved-search data."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from bson import ObjectId
from bson.errors import InvalidId
from pymongo.collection import Collection
from pymongo.database import Database

from cartrap.modules.search.models import SAVED_SEARCHES_COLLECTION, SEARCH_CATALOG_COLLECTION, SEARCH_CATALOG_DOCUMENT_ID


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

    def ensure_indexes(self) -> None:
        self.saved_searches.create_index([("owner_user_id", 1), ("criteria_key", 1)], unique=True)
        self.saved_searches.create_index([("owner_user_id", 1), ("created_at", -1)])

    def create_saved_search(self, payload: dict) -> dict:
        document = dict(payload)
        result = self.saved_searches.insert_one(document)
        document["_id"] = result.inserted_id
        return document

    def list_saved_searches_for_owner(self, owner_user_id: str) -> list[dict]:
        return list(self.saved_searches.find({"owner_user_id": owner_user_id}).sort("created_at", -1))

    def find_saved_search_by_owner_and_key(self, owner_user_id: str, criteria_key: str) -> Optional[dict]:
        return self.saved_searches.find_one({"owner_user_id": owner_user_id, "criteria_key": criteria_key})

    def find_saved_search_by_id_for_owner(self, saved_search_id: str, owner_user_id: str) -> Optional[dict]:
        try:
            object_id = ObjectId(saved_search_id)
        except (InvalidId, TypeError):
            return None
        return self.saved_searches.find_one({"_id": object_id, "owner_user_id": owner_user_id})

    def delete_saved_search(self, saved_search_id: str) -> None:
        self.saved_searches.delete_one({"_id": ObjectId(saved_search_id)})
