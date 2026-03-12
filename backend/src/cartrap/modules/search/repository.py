"""Mongo-backed persistence for search catalog data."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pymongo.collection import Collection
from pymongo.database import Database

from cartrap.modules.search.models import SEARCH_CATALOG_COLLECTION, SEARCH_CATALOG_DOCUMENT_ID


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
