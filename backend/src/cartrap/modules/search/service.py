"""Search service built on top of the Copart provider."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from fastapi import HTTPException, status
from pymongo.database import Database

from cartrap.modules.copart_provider.models import CopartSearchResult
from cartrap.modules.copart_provider.service import CopartProvider
from cartrap.modules.search.catalog_refresh import SearchCatalogRefreshJob
from cartrap.modules.search.repository import SearchCatalogRepository
from cartrap.modules.search.schemas import SearchRequest
from cartrap.modules.watchlist.service import WatchlistService


logger = logging.getLogger(__name__)
CATALOG_DATA_DIR = Path(__file__).with_name("data")
CATALOG_JSON_PATH = CATALOG_DATA_DIR / "copart_make_model_catalog.json"
CATALOG_OVERRIDES_PATH = CATALOG_DATA_DIR / "copart_make_model_overrides.json"


class SearchService:
    def __init__(
        self,
        database: Database,
        provider_factory: Optional[Callable[[], CopartProvider]] = None,
        watchlist_service_factory: Optional[Callable[[], WatchlistService]] = None,
        catalog_refresh_factory: Optional[Callable[[], SearchCatalogRefreshJob]] = None,
        catalog_seed_path: Optional[Path] = None,
    ) -> None:
        self._database = database
        self._provider_factory = provider_factory or CopartProvider
        self._watchlist_service_factory = watchlist_service_factory or (lambda: WatchlistService(database, provider_factory=provider_factory))
        self._catalog_seed_path = catalog_seed_path or CATALOG_JSON_PATH
        self._catalog_repository = SearchCatalogRepository(database)
        self._catalog_refresh_factory = catalog_refresh_factory or (
            lambda: SearchCatalogRefreshJob(provider_factory=self._provider_factory, overrides_path=CATALOG_OVERRIDES_PATH)
        )

    def search(self, payload: SearchRequest) -> dict:
        source_request = payload.to_api_request().to_payload()
        provider = self._provider_factory()
        try:
            results = provider.search_lots(source_request)
        except Exception as exc:
            logger.exception("Copart search failed for source_request=%s", source_request)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to fetch search results from Copart.",
            ) from exc
        finally:
            provider.close()
        return {"results": [self.serialize_result(item) for item in results], "source_request": source_request}

    def add_from_search(self, owner_user: dict, lot_url: str) -> dict:
        watchlist_service = self._watchlist_service_factory()
        return watchlist_service.add_tracked_lot(owner_user, lot_url)

    def ensure_catalog_seeded(self) -> None:
        self._catalog_repository.ensure_indexes()
        if self._catalog_repository.get_catalog() is not None:
            return
        if not self._catalog_seed_path.exists():
            logger.warning("Search catalog seed file is missing: %s", self._catalog_seed_path)
            return
        payload = json.loads(self._catalog_seed_path.read_text())
        self._catalog_repository.replace_catalog(payload, updated_at=datetime.now(timezone.utc))

    def get_catalog(self) -> dict:
        self.ensure_catalog_seeded()
        catalog = self._catalog_repository.get_catalog()
        if catalog is None:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Search catalog is not available.")
        return self.serialize_catalog(catalog)

    def refresh_catalog(self) -> dict:
        refresh_job = self._catalog_refresh_factory()
        try:
            catalog = refresh_job.refresh()
        except Exception as exc:
            logger.exception("Search catalog refresh failed.")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to refresh search catalog.",
            ) from exc
        self._catalog_repository.replace_catalog(catalog, updated_at=datetime.now(timezone.utc))
        stored_catalog = self._catalog_repository.get_catalog()
        if stored_catalog is None:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Search catalog refresh failed.")
        return self.serialize_catalog(stored_catalog)

    @staticmethod
    def serialize_result(item: CopartSearchResult) -> dict:
        return item.model_dump(mode="json")

    @staticmethod
    def serialize_catalog(catalog: dict) -> dict:
        makes = []
        for make in catalog.get("makes", []):
            models = [
                {
                    "slug": model["slug"],
                    "name": model["name"],
                    "search_filter": model["filter_query"],
                }
                for model in make.get("models", [])
            ]
            makes.append(
                {
                    "slug": make["slug"],
                    "name": make["name"],
                    "aliases": list(make.get("aliases", [])),
                    "search_filter": SearchService.combine_filter_queries(make.get("filter_queries", [])),
                    "models": models,
                }
            )
        return {
            "generated_at": catalog.get("generated_at"),
            "updated_at": catalog.get("updated_at"),
            "summary": catalog.get("summary", {}),
            "years": catalog.get("years", []),
            "makes": makes,
            "manual_override_count": int(catalog.get("manual_override_count", 0)),
        }

    @staticmethod
    def combine_filter_queries(filter_queries: list[str]) -> str:
        unique_filters = [query for index, query in enumerate(filter_queries) if query and query not in filter_queries[:index]]
        if not unique_filters:
            return ""
        if len(unique_filters) == 1:
            return unique_filters[0]
        return " OR ".join(f"({query})" for query in unique_filters)
