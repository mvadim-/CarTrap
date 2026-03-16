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
from cartrap.modules.system_status.service import SystemStatusService
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
        self._system_status_service = SystemStatusService(database)
        self._catalog_refresh_factory = catalog_refresh_factory or (
            lambda: SearchCatalogRefreshJob(provider_factory=self._provider_factory, overrides_path=CATALOG_OVERRIDES_PATH)
        )

    def search(self, payload: SearchRequest) -> dict:
        return self._execute_search(payload, live_sync_source="manual_search")

    def _execute_search(self, payload: SearchRequest, *, live_sync_source: str) -> dict:
        source_request = payload.to_api_request().to_payload()
        provider = self._provider_factory()
        try:
            first_page = provider.search_lots(source_request)
            self._system_status_service.mark_live_sync_available(live_sync_source)
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
            self._system_status_service.mark_live_sync_degraded(live_sync_source, exc)
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
        criteria.pop("seed_results", None)
        criteria_key = json.dumps(criteria, sort_keys=True)
        existing = self._saved_search_repository.find_saved_search_by_owner_and_key(owner_user["id"], criteria_key)
        if existing is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Search is already saved.")

        now = datetime.now(timezone.utc)
        stored_result_count = payload.result_count
        if stored_result_count is None and payload.seed_results:
            stored_result_count = len(payload.seed_results)
        document = self._saved_search_repository.create_saved_search(
            {
                "owner_user_id": owner_user["id"],
                "label": payload.label.strip() if payload.label else payload.display_title(),
                "criteria": criteria,
                "result_count": stored_result_count,
                "search_etag": None,
                "criteria_key": criteria_key,
                "last_checked_at": now,
                "created_at": now,
                "updated_at": now,
            }
        )
        cache_document = None
        if payload.seed_results:
            cache_document = self._saved_search_repository.upsert_saved_search_cache(
                str(document["_id"]),
                owner_user["id"],
                results=[item.model_dump(mode="json") for item in payload.seed_results],
                result_count=stored_result_count,
                new_lot_numbers=[],
                last_synced_at=now,
                seen_at=now,
                updated_at=now,
            )
        return {"saved_search": self.serialize_saved_search(document, cache_document=cache_document)}

    def list_saved_searches(self, owner_user: dict) -> dict:
        documents = self._saved_search_repository.list_saved_searches_for_owner(owner_user["id"])
        cache_documents = self._saved_search_repository.list_saved_search_caches_for_owner(
            owner_user["id"],
            [str(item["_id"]) for item in documents],
        )
        cache_by_saved_search_id = {str(item["saved_search_id"]): item for item in cache_documents}
        items = [self.serialize_saved_search(item, cache_document=cache_by_saved_search_id.get(str(item["_id"]))) for item in documents]
        return {"items": items}

    def remove_saved_search(self, owner_user: dict, saved_search_id: str) -> None:
        self._get_saved_search_or_404(owner_user, saved_search_id)
        self._saved_search_repository.delete_saved_search(saved_search_id)

    def view_saved_search(self, owner_user: dict, saved_search_id: str) -> dict:
        saved_search = self._get_saved_search_or_404(owner_user, saved_search_id)
        viewed_at = datetime.now(timezone.utc)
        viewed_cache = self._saved_search_repository.mark_saved_search_cache_viewed(
            saved_search_id,
            owner_user["id"],
            seen_at=viewed_at,
            updated_at=viewed_at,
        )
        response = self.serialize_saved_search_cache_view(saved_search, viewed_cache)
        if viewed_cache is not None:
            cleared_cache = dict(viewed_cache)
            cleared_cache["new_lot_numbers"] = []
            cleared_cache["seen_at"] = viewed_at
            response["saved_search"] = self.serialize_saved_search(saved_search, cache_document=cleared_cache)
        return response

    def refresh_saved_search_live(self, owner_user: dict, saved_search_id: str) -> dict:
        saved_search = self._get_saved_search_or_404(owner_user, saved_search_id)
        criteria = SearchRequest(**saved_search["criteria"])
        refreshed_at = datetime.now(timezone.utc)
        search_response = self._execute_search(criteria, live_sync_source="saved_search_refresh")
        cache_document = self._saved_search_repository.upsert_saved_search_cache(
            saved_search_id,
            owner_user["id"],
            results=search_response["results"],
            result_count=search_response["total_results"],
            new_lot_numbers=[],
            last_synced_at=refreshed_at,
            seen_at=refreshed_at,
            updated_at=refreshed_at,
        )
        updated_saved_search = self._saved_search_repository.update_saved_search_poll_state(
            saved_search_id,
            result_count=search_response["total_results"],
            last_checked_at=refreshed_at,
            updated_at=refreshed_at,
            search_etag=saved_search.get("search_etag"),
        )
        if updated_saved_search is None:
            updated_saved_search = saved_search
        return self.serialize_saved_search_cache_view(updated_saved_search, cache_document)

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
            self._system_status_service.mark_live_sync_available("catalog_refresh")
        except Exception as exc:
            self._system_status_service.mark_live_sync_degraded("catalog_refresh", exc)
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
            except Exception as exc:
                failed += 1
                self._system_status_service.mark_live_sync_degraded("saved_search_poll", exc, checked_at=current_time)
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
        saved_search_id = str(saved_search["_id"])
        cache_document = self._saved_search_repository.find_saved_search_cache_by_id_for_owner(
            saved_search_id,
            saved_search["owner_user_id"],
        )
        fetch_result = self.fetch_result_count(criteria, etag=saved_search.get("search_etag"), checked_at=now)
        if fetch_result["not_modified"] and cache_document is not None:
            self._saved_search_repository.update_saved_search_poll_state(
                saved_search_id,
                result_count=int(saved_search.get("result_count") or 0),
                last_checked_at=now,
                updated_at=now,
                search_etag=fetch_result.get("etag"),
            )
            return None

        search_response = self._execute_search(criteria, live_sync_source="saved_search_poll")
        next_result_count = search_response["total_results"]
        previous_result_count = saved_search.get("result_count")
        current_lot_numbers = self._ordered_unique_lot_numbers(search_response["results"])
        merged_new_lot_numbers, truly_new_lot_numbers = self._compute_saved_search_new_lot_numbers(
            cache_document,
            current_lot_numbers=current_lot_numbers,
        )
        refreshed_cache = self._saved_search_repository.upsert_saved_search_cache(
            saved_search_id,
            saved_search["owner_user_id"],
            results=search_response["results"],
            result_count=next_result_count,
            new_lot_numbers=merged_new_lot_numbers,
            last_synced_at=now,
            seen_at=cache_document.get("seen_at") if cache_document is not None else None,
            updated_at=now,
        )
        self._saved_search_repository.update_saved_search_poll_state(
            saved_search_id,
            result_count=next_result_count,
            last_checked_at=now,
            updated_at=now,
            search_etag=fetch_result.get("etag"),
        )

        display_title = criteria.display_title() or saved_search.get("label") or "Saved Search"
        return {
            "saved_search_id": saved_search_id,
            "owner_user_id": saved_search["owner_user_id"],
            "search_label": saved_search.get("label") or display_title,
            "search_title": display_title,
            "previous_result_count": previous_result_count,
            "result_count": next_result_count,
            "new_matches": len(truly_new_lot_numbers),
            "new_lot_numbers": truly_new_lot_numbers,
            "cached_new_count": len(refreshed_cache.get("new_lot_numbers", [])),
        }

    def fetch_result_count(self, payload: SearchRequest, etag: str | None = None, checked_at: datetime | None = None) -> dict:
        source_request = payload.to_api_request().to_payload()
        provider = self._provider_factory()
        try:
            if hasattr(provider, "fetch_search_count_conditional"):
                result = provider.fetch_search_count_conditional(source_request, etag=etag)
                if result.not_modified:
                    self._system_status_service.mark_live_sync_available(
                        "saved_search_poll",
                        checked_at=checked_at,
                    )
                    return {"result_count": None, "etag": result.etag, "not_modified": True}
                self._system_status_service.mark_live_sync_available("saved_search_poll", checked_at=checked_at)
                return {"result_count": int(result.num_found or 0), "etag": result.etag, "not_modified": False}
            first_page = provider.search_lots(source_request)
            self._system_status_service.mark_live_sync_available("saved_search_poll", checked_at=checked_at)
        except Exception as exc:
            self._system_status_service.mark_live_sync_degraded("saved_search_poll", exc, checked_at=checked_at)
            logger.exception("Copart result-count fetch failed for source_request=%s", source_request)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to fetch search results from Copart.",
            ) from exc
        finally:
            provider.close()
        return {"result_count": first_page.num_found, "etag": None, "not_modified": False}

    def _get_saved_search_or_404(self, owner_user: dict, saved_search_id: str) -> dict:
        saved_search = self._saved_search_repository.find_saved_search_by_id_for_owner(saved_search_id, owner_user["id"])
        if saved_search is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Saved search not found.")
        return saved_search

    @staticmethod
    def _ordered_unique_lot_numbers(results: list[dict]) -> list[str]:
        ordered: list[str] = []
        for item in results:
            lot_number = item.get("lot_number")
            if not lot_number or lot_number in ordered:
                continue
            ordered.append(lot_number)
        return ordered

    @staticmethod
    def _compute_saved_search_new_lot_numbers(
        cache_document: dict | None,
        *,
        current_lot_numbers: list[str],
    ) -> tuple[list[str], list[str]]:
        if cache_document is None:
            return [], []

        previous_lot_numbers = SearchService._ordered_unique_lot_numbers(cache_document.get("results", []))
        previous_lot_numbers_set = set(previous_lot_numbers)
        unseen_lot_numbers_set = set(cache_document.get("new_lot_numbers", []))
        truly_new_lot_numbers = [lot_number for lot_number in current_lot_numbers if lot_number not in previous_lot_numbers_set]
        merged_new_lot_numbers = [
            lot_number
            for lot_number in current_lot_numbers
            if lot_number in unseen_lot_numbers_set or lot_number in truly_new_lot_numbers
        ]
        return merged_new_lot_numbers, truly_new_lot_numbers

    @staticmethod
    def serialize_result(item: CopartSearchResult) -> dict:
        return item.model_dump(mode="json")

    @staticmethod
    def serialize_saved_search(document: dict, cache_document: dict | None = None) -> dict:
        criteria = document.get("criteria", {})
        search_request = SearchRequest(**criteria)
        cache_metadata = SearchService.serialize_saved_search_cache_metadata(cache_document)
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
            "cached_result_count": cache_metadata["cached_result_count"],
            "new_count": cache_metadata["new_count"],
            "last_synced_at": cache_metadata["last_synced_at"],
            "created_at": document["created_at"],
        }

    @staticmethod
    def serialize_saved_search_cache_metadata(cache_document: dict | None) -> dict:
        if cache_document is None:
            return {
                "cached_result_count": None,
                "new_count": 0,
                "last_synced_at": None,
            }
        return {
            "cached_result_count": cache_document.get("result_count"),
            "new_count": len(cache_document.get("new_lot_numbers", [])),
            "last_synced_at": cache_document.get("last_synced_at"),
        }

    @staticmethod
    def serialize_saved_search_cache_view(document: dict, cache_document: dict | None) -> dict:
        serialized_saved_search = SearchService.serialize_saved_search(document, cache_document=cache_document)
        if cache_document is None:
            return {
                "saved_search": serialized_saved_search,
                "results": [],
                "cached_result_count": 0,
                "new_count": 0,
                "last_synced_at": None,
                "seen_at": None,
            }

        new_lot_numbers = set(cache_document.get("new_lot_numbers", []))
        return {
            "saved_search": serialized_saved_search,
            "results": [
                {
                    **item,
                    "is_new": item.get("lot_number") in new_lot_numbers,
                }
                for item in cache_document.get("results", [])
            ],
            "cached_result_count": int(cache_document.get("result_count") or 0),
            "new_count": len(new_lot_numbers),
            "last_synced_at": cache_document.get("last_synced_at"),
            "seen_at": cache_document.get("seen_at"),
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
