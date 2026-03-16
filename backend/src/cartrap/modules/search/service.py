"""Search service built on top of the Copart provider."""

from __future__ import annotations

import json
import logging
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional

from fastapi import HTTPException, status
from pymongo.database import Database

from cartrap.modules.copart_provider.models import CopartSearchResult
from cartrap.modules.copart_provider.service import CopartProvider
from cartrap.modules.notifications.service import NotificationService
from cartrap.modules.search.catalog_refresh import SearchCatalogRefreshJob
from cartrap.modules.search.repository import SavedSearchRepository, SearchCatalogRepository
from cartrap.modules.search.schemas import SavedSearchCreateRequest, SearchRequest
from cartrap.modules.watchlist.service import WatchlistService


logger = logging.getLogger(__name__)
CATALOG_DATA_DIR = Path(__file__).with_name("data")
CATALOG_JSON_PATH = CATALOG_DATA_DIR / "copart_make_model_catalog.json"
CATALOG_OVERRIDES_PATH = CATALOG_DATA_DIR / "copart_make_model_overrides.json"
SEARCH_PAGE_SIZE = 20
SAVED_SEARCH_POLL_INTERVAL_MINUTES = 15


class SearchService:
    def __init__(
        self,
        database: Database,
        provider_factory: Optional[Callable[[], CopartProvider]] = None,
        watchlist_service_factory: Optional[Callable[[], WatchlistService]] = None,
        catalog_refresh_factory: Optional[Callable[[], SearchCatalogRefreshJob]] = None,
        catalog_seed_path: Optional[Path] = None,
        notification_service: Optional[NotificationService] = None,
    ) -> None:
        self._database = database
        self._provider_factory = provider_factory or CopartProvider
        self._watchlist_service_factory = watchlist_service_factory or (lambda: WatchlistService(database, provider_factory=provider_factory))
        self._catalog_seed_path = catalog_seed_path or CATALOG_JSON_PATH
        self._catalog_repository = SearchCatalogRepository(database)
        self._saved_search_repository = SavedSearchRepository(database)
        self._saved_search_repository.ensure_indexes()
        self._notification_service = notification_service
        self._catalog_refresh_factory = catalog_refresh_factory or (
            lambda: SearchCatalogRefreshJob(provider_factory=self._provider_factory, overrides_path=CATALOG_OVERRIDES_PATH)
        )

    def search(self, payload: SearchRequest) -> dict:
        source_request = payload.to_api_request().to_payload()
        provider = self._provider_factory()
        try:
            first_page = provider.search_lots(source_request)
            total_results = first_page.num_found
            results_by_lot_number = {item.lot_number: item for item in first_page.results}
            total_pages = max(1, math.ceil(total_results / SEARCH_PAGE_SIZE)) if total_results else 1

            for page_number in range(2, total_pages + 1):
                page_request = dict(source_request)
                page_request["pageNumber"] = page_number
                page = provider.search_lots(page_request)
                for item in page.results:
                    results_by_lot_number[item.lot_number] = item
        except Exception as exc:
            logger.exception("Copart search failed for source_request=%s", source_request)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to fetch search results from Copart.",
            ) from exc
        finally:
            provider.close()
        return {
            "results": [self.serialize_result(item) for item in results_by_lot_number.values()],
            "total_results": total_results,
            "source_request": source_request,
        }

    def add_from_search(self, owner_user: dict, lot_url: str) -> dict:
        watchlist_service = self._watchlist_service_factory()
        return watchlist_service.add_tracked_lot(owner_user, lot_url)

    def save_search(self, owner_user: dict, payload: SavedSearchCreateRequest) -> dict:
        criteria = payload.normalized_criteria()
        criteria_key = json.dumps(criteria, sort_keys=True)
        existing = self._saved_search_repository.find_saved_search_by_owner_and_key(owner_user["id"], criteria_key)
        if existing is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Search is already saved.")

        now = datetime.now(timezone.utc)
        document = self._saved_search_repository.create_saved_search(
            {
                "owner_user_id": owner_user["id"],
                "label": payload.label.strip() if payload.label else payload.display_title(),
                "criteria": criteria,
                "result_count": payload.result_count,
                "search_etag": None,
                "criteria_key": criteria_key,
                "last_checked_at": now,
                "created_at": now,
                "updated_at": now,
            }
        )
        return {"saved_search": self.serialize_saved_search(document)}

    def list_saved_searches(self, owner_user: dict) -> dict:
        items = [self.serialize_saved_search(item) for item in self._saved_search_repository.list_saved_searches_for_owner(owner_user["id"])]
        return {"items": items}

    def remove_saved_search(self, owner_user: dict, saved_search_id: str) -> None:
        saved_search = self._saved_search_repository.find_saved_search_by_id_for_owner(saved_search_id, owner_user["id"])
        if saved_search is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Saved search not found.")
        self._saved_search_repository.delete_saved_search(saved_search_id)

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

    def poll_due_saved_searches(self, now: datetime | None = None) -> dict:
        current_time = now or datetime.now(timezone.utc)
        due_before = current_time - timedelta(minutes=SAVED_SEARCH_POLL_INTERVAL_MINUTES)
        processed = 0
        updated = 0
        failed = 0
        notified = 0
        events: list[dict] = []

        for saved_search in self._saved_search_repository.list_due_saved_searches(due_before):
            processed += 1
            try:
                event = self._poll_single_saved_search(saved_search, current_time)
            except Exception:
                failed += 1
                logger.exception("Saved search polling failed for saved_search_id=%s", saved_search.get("_id"))
                continue

            if event is None:
                continue

            updated += 1
            events.append(event)

            if event["new_matches"] > 0 and self._notification_service is not None:
                delivery = self._notification_service.send_saved_search_match_notification(event)
                notified += delivery["delivered"]

        return {
            "processed": processed,
            "updated": updated,
            "failed": failed,
            "notified": notified,
            "events": events,
        }

    def _poll_single_saved_search(self, saved_search: dict, now: datetime) -> dict | None:
        criteria = SearchRequest(**saved_search["criteria"])
        fetch_result = self.fetch_result_count(criteria, etag=saved_search.get("search_etag"))
        if fetch_result["not_modified"]:
            self._saved_search_repository.update_saved_search_poll_state(
                str(saved_search["_id"]),
                result_count=int(saved_search.get("result_count") or 0),
                last_checked_at=now,
                updated_at=now,
                search_etag=fetch_result.get("etag"),
            )
            return None

        next_result_count = fetch_result["result_count"]
        previous_result_count = saved_search.get("result_count")
        self._saved_search_repository.update_saved_search_poll_state(
            str(saved_search["_id"]),
            result_count=next_result_count,
            last_checked_at=now,
            updated_at=now,
            search_etag=fetch_result.get("etag"),
        )

        if previous_result_count == next_result_count:
            return None

        display_title = criteria.display_title() or saved_search.get("label") or "Saved Search"
        new_matches = 0
        if previous_result_count is not None and next_result_count > previous_result_count:
            new_matches = next_result_count - previous_result_count

        return {
            "saved_search_id": str(saved_search["_id"]),
            "owner_user_id": saved_search["owner_user_id"],
            "search_label": saved_search.get("label") or display_title,
            "search_title": display_title,
            "previous_result_count": previous_result_count,
            "result_count": next_result_count,
            "new_matches": new_matches,
        }

    def fetch_result_count(self, payload: SearchRequest, etag: str | None = None) -> dict:
        source_request = payload.to_api_request().to_payload()
        provider = self._provider_factory()
        try:
            if hasattr(provider, "fetch_search_count_conditional"):
                result = provider.fetch_search_count_conditional(source_request, etag=etag)
                if result.not_modified:
                    return {"result_count": None, "etag": result.etag, "not_modified": True}
                return {"result_count": int(result.num_found or 0), "etag": result.etag, "not_modified": False}
            first_page = provider.search_lots(source_request)
        except Exception as exc:
            logger.exception("Copart result-count fetch failed for source_request=%s", source_request)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to fetch search results from Copart.",
            ) from exc
        finally:
            provider.close()
        return {"result_count": first_page.num_found, "etag": None, "not_modified": False}

    @staticmethod
    def serialize_result(item: CopartSearchResult) -> dict:
        return item.model_dump(mode="json")

    @staticmethod
    def serialize_saved_search(document: dict) -> dict:
        criteria = document.get("criteria", {})
        search_request = SearchRequest(**criteria)
        return {
            "id": str(document["_id"]),
            "label": document["label"],
            "criteria": {
                "make": criteria.get("make"),
                "model": criteria.get("model"),
                "make_filter": criteria.get("make_filter"),
                "model_filter": criteria.get("model_filter"),
                "drive_type": criteria.get("drive_type"),
                "primary_damage": criteria.get("primary_damage"),
                "title_type": criteria.get("title_type"),
                "fuel_type": criteria.get("fuel_type"),
                "lot_condition": criteria.get("lot_condition"),
                "odometer_range": criteria.get("odometer_range"),
                "year_from": criteria.get("year_from"),
                "year_to": criteria.get("year_to"),
                "lot_number": criteria.get("lot_number"),
            },
            "external_url": search_request.to_external_url(),
            "result_count": document.get("result_count"),
            "created_at": document["created_at"],
        }

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
