"""Search service built on top of the Copart provider."""

from __future__ import annotations

import json
import logging
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import perf_counter
from typing import Callable, Optional

from fastapi import HTTPException, status
from pymongo.database import Database

from cartrap.core.logging import make_log_extra, new_correlation_id
from cartrap.modules.copart_provider.models import CopartSearchResult
from cartrap.modules.copart_provider.service import CopartProvider
from cartrap.modules.notifications.service import NotificationService
from cartrap.modules.monitoring.job_runtime import JobRuntimeService
from cartrap.modules.search.catalog_refresh import SearchCatalogRefreshJob
from cartrap.modules.search.repository import SavedSearchRepository, SearchCatalogRepository
from cartrap.modules.search.schemas import SavedSearchCreateRequest, SearchRequest
from cartrap.modules.system_status.service import SystemStatusService, build_freshness_envelope
from cartrap.modules.watchlist.service import WatchlistService


logger = logging.getLogger(__name__)
CATALOG_DATA_DIR = Path(__file__).with_name("data")
CATALOG_JSON_PATH = CATALOG_DATA_DIR / "copart_make_model_catalog.json"
CATALOG_OVERRIDES_PATH = CATALOG_DATA_DIR / "copart_make_model_overrides.json"
SEARCH_PAGE_SIZE = 20
DEFAULT_SAVED_SEARCH_POLL_INTERVAL_MINUTES = 15


class SearchService:
    def __init__(
        self,
        database: Database,
        provider_factory: Optional[Callable[[], CopartProvider]] = None,
        watchlist_service_factory: Optional[Callable[[], WatchlistService]] = None,
        catalog_refresh_factory: Optional[Callable[[], SearchCatalogRefreshJob]] = None,
        catalog_seed_path: Optional[Path] = None,
        notification_service: Optional[NotificationService] = None,
        saved_search_poll_interval_minutes: int = DEFAULT_SAVED_SEARCH_POLL_INTERVAL_MINUTES,
        refresh_job_runtime: JobRuntimeService | None = None,
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
        self._saved_search_poll_interval_minutes = saved_search_poll_interval_minutes
        self._refresh_job_runtime = refresh_job_runtime or JobRuntimeService(database)
        self._catalog_refresh_factory = catalog_refresh_factory or (
            lambda: SearchCatalogRefreshJob(provider_factory=self._provider_factory, overrides_path=CATALOG_OVERRIDES_PATH)
        )

    def search(self, payload: SearchRequest) -> dict:
        return self._execute_search(payload, live_sync_source="manual_search")

    def _execute_search(self, payload: SearchRequest, *, live_sync_source: str) -> dict:
        correlation_id = new_correlation_id(live_sync_source)
        started_at = perf_counter()
        source_request = payload.to_api_request().to_payload()
        logger.info(
            "search.execute.start",
            extra=make_log_extra(
                "search.execute.start",
                correlation_id=correlation_id,
                source=live_sync_source,
                lot_number=payload.lot_number,
                make=payload.make,
                model=payload.model,
            ),
        )
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
            logger.exception(
                "search.execute.failed",
                extra=make_log_extra(
                    "search.execute.failed",
                    correlation_id=correlation_id,
                    source=live_sync_source,
                    duration_ms=round((perf_counter() - started_at) * 1000, 2),
                    error_type=type(exc).__name__,
                    source_request=source_request,
                ),
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to fetch search results from Copart.",
            ) from exc
        finally:
            provider.close()
        logger.info(
            "search.execute.success",
            extra=make_log_extra(
                "search.execute.success",
                correlation_id=correlation_id,
                source=live_sync_source,
                duration_ms=round((perf_counter() - started_at) * 1000, 2),
                total_results=total_results,
                page_count=total_pages,
            ),
        )
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
                "last_refresh_attempted_at": now if payload.seed_results else None,
                "last_refresh_succeeded_at": now if payload.seed_results else None,
                "next_refresh_retry_at": None,
                "last_refresh_error": None,
                "last_refresh_retryable": False,
                "refresh_status": "idle",
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
        live_sync_status = self._system_status_service.get_live_sync_status()
        return {
            "saved_search": self.serialize_saved_search(
                document,
                cache_document=cache_document,
                live_sync_status=live_sync_status,
            )
        }

    def list_saved_searches(self, owner_user: dict) -> dict:
        documents = self._saved_search_repository.list_saved_searches_for_owner(owner_user["id"])
        cache_documents = self._saved_search_repository.list_saved_search_caches_for_owner(
            owner_user["id"],
            [str(item["_id"]) for item in documents],
        )
        cache_by_saved_search_id = {str(item["saved_search_id"]): item for item in cache_documents}
        live_sync_status = self._system_status_service.get_live_sync_status()
        items = [
            self.serialize_saved_search(
                item,
                cache_document=cache_by_saved_search_id.get(str(item["_id"])),
                live_sync_status=live_sync_status,
            )
            for item in documents
        ]
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
        live_sync_status = self._system_status_service.get_live_sync_status()
        response = self.serialize_saved_search_cache_view(
            saved_search,
            viewed_cache,
            live_sync_status=live_sync_status,
        )
        if viewed_cache is not None:
            cleared_cache = dict(viewed_cache)
            cleared_cache["new_lot_numbers"] = []
            cleared_cache["seen_at"] = viewed_at
            response["saved_search"] = self.serialize_saved_search(
                saved_search,
                cache_document=cleared_cache,
                live_sync_status=live_sync_status,
            )
        return response

    def refresh_saved_search_live(self, owner_user: dict, saved_search_id: str) -> dict:
        saved_search = self._get_saved_search_or_404(owner_user, saved_search_id)
        criteria = SearchRequest(**saved_search["criteria"])
        refreshed_at = datetime.now(timezone.utc)
        correlation_id = new_correlation_id("saved-search-refresh")
        started_at = perf_counter()
        logger.info(
            "saved_search.refresh.start",
            extra=make_log_extra(
                "saved_search.refresh.start",
                correlation_id=correlation_id,
                saved_search_id=saved_search_id,
                owner_user_id=owner_user["id"],
                priority_class="manual",
            ),
        )
        try:
            search_response = self._execute_search(criteria, live_sync_source="saved_search_refresh")
        except HTTPException as exc:
            retryable, error_message = self.classify_refresh_exception(exc)
            self._saved_search_repository.update_saved_search_refresh_state(
                saved_search_id,
                {
                    **self._build_refresh_failure_payload(
                        refreshed_at,
                        error_message=error_message,
                        retryable=retryable,
                    ),
                    "last_refresh_priority_class": "manual",
                },
            )
            logger.warning(
                "saved_search.refresh.failed",
                extra=make_log_extra(
                    "saved_search.refresh.failed",
                    correlation_id=correlation_id,
                    saved_search_id=saved_search_id,
                    owner_user_id=owner_user["id"],
                    duration_ms=round((perf_counter() - started_at) * 1000, 2),
                    retryable=retryable,
                    error_message=error_message,
                ),
            )
            raise
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
        self._saved_search_repository.update_saved_search_refresh_state(
            saved_search_id,
            {
                **self._build_refresh_success_payload(refreshed_at),
                "last_refresh_priority_class": "manual",
                "last_refresh_new_matches": 0,
                "last_refresh_cached_new_count": 0,
            },
        )
        if updated_saved_search is None:
            updated_saved_search = saved_search
        live_sync_status = self._system_status_service.get_live_sync_status()
        logger.info(
            "saved_search.refresh.success",
            extra=make_log_extra(
                "saved_search.refresh.success",
                correlation_id=correlation_id,
                saved_search_id=saved_search_id,
                owner_user_id=owner_user["id"],
                duration_ms=round((perf_counter() - started_at) * 1000, 2),
                result_count=search_response["total_results"],
                priority_class="manual",
            ),
        )
        return self.serialize_saved_search_cache_view(
            updated_saved_search,
            cache_document,
            live_sync_status=live_sync_status,
        )

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
        correlation_id = new_correlation_id("catalog-refresh")
        started_at = perf_counter()
        logger.info(
            "search_catalog.refresh.start",
            extra=make_log_extra(
                "search_catalog.refresh.start",
                correlation_id=correlation_id,
            ),
        )
        try:
            catalog = refresh_job.refresh()
            self._system_status_service.mark_live_sync_available("catalog_refresh")
        except Exception as exc:
            self._system_status_service.mark_live_sync_degraded("catalog_refresh", exc)
            logger.exception(
                "search_catalog.refresh.failed",
                extra=make_log_extra(
                    "search_catalog.refresh.failed",
                    correlation_id=correlation_id,
                    duration_ms=round((perf_counter() - started_at) * 1000, 2),
                    error_type=type(exc).__name__,
                ),
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to refresh search catalog.",
            ) from exc
        self._catalog_repository.replace_catalog(catalog, updated_at=datetime.now(timezone.utc))
        stored_catalog = self._catalog_repository.get_catalog()
        if stored_catalog is None:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Search catalog refresh failed.")
        logger.info(
            "search_catalog.refresh.success",
            extra=make_log_extra(
                "search_catalog.refresh.success",
                correlation_id=correlation_id,
                duration_ms=round((perf_counter() - started_at) * 1000, 2),
                make_count=int(catalog.get("summary", {}).get("make_count", 0)),
                model_count=int(catalog.get("summary", {}).get("model_count", 0)),
            ),
        )
        return self.serialize_catalog(stored_catalog)

    def poll_due_saved_searches(self, now: datetime | None = None) -> dict:
        current_time = now or datetime.now(timezone.utc)
        due_before = current_time - timedelta(minutes=self._saved_search_poll_interval_minutes)
        processed = 0
        updated = 0
        failed = 0
        notified = 0
        skipped = 0
        events: list[dict] = []
        jobs: list[dict] = []
        due_saved_searches = self._saved_search_repository.list_due_saved_searches(due_before)
        due_saved_searches.sort(key=self._saved_search_priority_sort_key)

        for saved_search in due_saved_searches:
            saved_search_id = str(saved_search["_id"])
            priority_class = self._saved_search_priority_class(saved_search)
            correlation_id = new_correlation_id("saved-search-poll")
            started_at = perf_counter()
            runtime = self._refresh_job_runtime.acquire(
                job_type="saved_search_poll",
                resource_id=saved_search_id,
                now=current_time,
                metadata={"owner_user_id": saved_search["owner_user_id"], "priority_class": priority_class},
            )
            if runtime is None:
                skipped += 1
                jobs.append(
                    self._refresh_job_runtime.describe_skip(
                        job_type="saved_search_poll",
                        resource_id=saved_search_id,
                        now=current_time,
                    )
                )
                continue

            processed += 1
            last_checked_at = saved_search.get("last_checked_at")
            stale_for_seconds = (
                round((current_time - last_checked_at).total_seconds(), 2) if isinstance(last_checked_at, datetime) else None
            )
            logger.info(
                "saved_search.poll.start",
                extra=make_log_extra(
                    "saved_search.poll.start",
                    correlation_id=correlation_id,
                    saved_search_id=saved_search_id,
                    owner_user_id=saved_search["owner_user_id"],
                    priority_class=priority_class,
                    stale_for_seconds=stale_for_seconds,
                    attempt_count=runtime.get("attempt_count"),
                ),
            )
            try:
                event = self._poll_single_saved_search(saved_search, current_time)
            except Exception as exc:
                failed += 1
                self._system_status_service.mark_live_sync_degraded("saved_search_poll", exc, checked_at=current_time)
                retryable = True
                error_message = str(exc).strip() or "Saved search refresh failed."
                if isinstance(exc, HTTPException):
                    retryable, error_message = self.classify_refresh_exception(exc)
                self._saved_search_repository.update_saved_search_refresh_state(
                    saved_search_id,
                    {
                        **self._build_refresh_failure_payload(
                            current_time,
                            error_message=error_message,
                            retryable=retryable,
                        ),
                        "last_refresh_priority_class": priority_class,
                    },
                )
                jobs.append(
                    (
                        self._refresh_job_runtime.fail_retryable(
                            runtime,
                            now=current_time,
                            outcome="refresh_failed",
                            error_message=error_message,
                            metadata={"owner_user_id": saved_search["owner_user_id"], "priority_class": priority_class},
                        )
                        if retryable
                        else self._refresh_job_runtime.fail_non_retryable(
                            runtime,
                            now=current_time,
                            outcome="refresh_failed",
                            error_message=error_message,
                            metadata={"owner_user_id": saved_search["owner_user_id"], "priority_class": priority_class},
                        )
                    )
                )
                logger.exception(
                    "saved_search.poll.failed",
                    extra=make_log_extra(
                        "saved_search.poll.failed",
                        correlation_id=correlation_id,
                        saved_search_id=saved_search_id,
                        owner_user_id=saved_search["owner_user_id"],
                        priority_class=priority_class,
                        duration_ms=round((perf_counter() - started_at) * 1000, 2),
                        retryable=retryable,
                        error_message=error_message,
                    ),
                )
                continue

            if event is None:
                self._saved_search_repository.update_saved_search_refresh_state(
                    saved_search_id,
                    {
                        **self._build_refresh_success_payload(current_time),
                        "last_refresh_priority_class": priority_class,
                        "last_refresh_outcome": "not_modified",
                        "last_refresh_new_matches": 0,
                        "last_refresh_cached_new_count": 0,
                    },
                )
                jobs.append(
                    self._refresh_job_runtime.complete(
                        runtime,
                        now=current_time,
                        outcome="not_modified",
                        metadata={
                            "owner_user_id": saved_search["owner_user_id"],
                            "updated": False,
                            "priority_class": priority_class,
                        },
                    )
                )
                logger.info(
                    "saved_search.poll.success",
                    extra=make_log_extra(
                        "saved_search.poll.success",
                        correlation_id=correlation_id,
                        saved_search_id=saved_search_id,
                        owner_user_id=saved_search["owner_user_id"],
                        priority_class=priority_class,
                        duration_ms=round((perf_counter() - started_at) * 1000, 2),
                        outcome="not_modified",
                        new_matches=0,
                        cached_new_count=0,
                    ),
                )
                continue

            updated += 1
            events.append(event)
            delivery = {"delivered": 0, "failed": 0, "removed": 0, "endpoints": []}

            if event["new_matches"] > 0 and self._notification_service is not None:
                delivery = self._notification_service.send_saved_search_match_notification(event)
                notified += delivery["delivered"]
            self._saved_search_repository.update_saved_search_refresh_state(
                saved_search_id,
                {
                    **self._build_refresh_success_payload(current_time),
                    "last_refresh_priority_class": priority_class,
                    "last_refresh_new_matches": event["new_matches"],
                    "last_refresh_cached_new_count": event["cached_new_count"],
                },
            )
            jobs.append(
                self._refresh_job_runtime.complete(
                    runtime,
                    now=current_time,
                    outcome="refreshed",
                    metadata={
                        "owner_user_id": saved_search["owner_user_id"],
                        "updated": True,
                        "priority_class": priority_class,
                        "new_matches": event["new_matches"],
                        "notified": delivery["delivered"],
                        "cached_new_count": event["cached_new_count"],
                    },
                )
            )
            logger.info(
                "saved_search.poll.success",
                extra=make_log_extra(
                    "saved_search.poll.success",
                    correlation_id=correlation_id,
                    saved_search_id=saved_search_id,
                    owner_user_id=saved_search["owner_user_id"],
                    priority_class=priority_class,
                    duration_ms=round((perf_counter() - started_at) * 1000, 2),
                    outcome="refreshed",
                    new_matches=event["new_matches"],
                    cached_new_count=event["cached_new_count"],
                    delivered_notifications=delivery["delivered"],
                ),
            )

        return {
            "processed": processed,
            "updated": updated,
            "failed": failed,
            "notified": notified,
            "skipped": skipped,
            "events": events,
            "jobs": jobs,
        }

    def _saved_search_priority_class(self, saved_search: dict) -> str:
        cache_document = self._saved_search_repository.find_saved_search_cache_by_id_for_owner(
            str(saved_search["_id"]),
            saved_search["owner_user_id"],
        )
        if cache_document is not None and cache_document.get("new_lot_numbers"):
            return "recently_changed"
        if saved_search.get("last_checked_at") is None:
            return "normal"
        return "cold"

    def _saved_search_priority_sort_key(self, saved_search: dict) -> tuple[int, datetime]:
        order = {"recently_changed": 0, "normal": 1, "cold": 2}
        last_checked_at = saved_search.get("last_checked_at") or datetime.fromtimestamp(0, timezone.utc)
        return (order[self._saved_search_priority_class(saved_search)], last_checked_at)

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
            self._saved_search_repository.update_saved_search_refresh_state(
                saved_search_id,
                self._build_refresh_success_payload(now),
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
        self._saved_search_repository.update_saved_search_refresh_state(
            saved_search_id,
            self._build_refresh_success_payload(now),
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

    def serialize_saved_search(
        self,
        document: dict,
        cache_document: dict | None = None,
        live_sync_status: dict | None = None,
    ) -> dict:
        criteria = document.get("criteria", {})
        search_request = SearchRequest(**criteria)
        cache_metadata = self.serialize_saved_search_cache_metadata(cache_document)
        freshness = build_freshness_envelope(
            last_synced_at=cache_metadata["last_synced_at"],
            stale_after_window=timedelta(minutes=self._saved_search_poll_interval_minutes),
            live_sync_status=live_sync_status,
        )
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
            "freshness": freshness,
            "refresh_state": self.serialize_refresh_state(document),
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

    def serialize_saved_search_cache_view(
        self,
        document: dict,
        cache_document: dict | None,
        live_sync_status: dict | None = None,
    ) -> dict:
        serialized_saved_search = self.serialize_saved_search(
            document,
            cache_document=cache_document,
            live_sync_status=live_sync_status,
        )
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

    @staticmethod
    def serialize_refresh_state(document: dict) -> dict:
        status = document.get("refresh_status") or "idle"
        return {
            "status": status,
            "last_attempted_at": document.get("last_refresh_attempted_at"),
            "last_succeeded_at": document.get("last_refresh_succeeded_at"),
            "next_retry_at": document.get("next_refresh_retry_at"),
            "error_message": document.get("last_refresh_error"),
            "retryable": bool(document.get("last_refresh_retryable", False)),
            "priority_class": document.get("last_refresh_priority_class"),
            "last_outcome": document.get("last_refresh_outcome"),
            "metrics": {
                "new_matches": int(document.get("last_refresh_new_matches") or 0),
                "cached_new_count": int(document.get("last_refresh_cached_new_count") or 0),
            },
        }

    @staticmethod
    def classify_refresh_exception(exc: HTTPException) -> tuple[bool, str]:
        detail = str(exc.detail).strip() if getattr(exc, "detail", None) else str(exc)
        if exc.status_code >= 500:
            return True, detail or "Refresh failed."
        return False, detail or "Refresh failed."

    @staticmethod
    def _build_refresh_success_payload(now: datetime) -> dict:
        return {
            "last_refresh_attempted_at": now,
            "last_refresh_succeeded_at": now,
            "next_refresh_retry_at": None,
            "last_refresh_error": None,
            "last_refresh_retryable": False,
            "refresh_status": "idle",
            "last_refresh_outcome": "refreshed",
            "updated_at": now,
        }

    @staticmethod
    def _build_refresh_failure_payload(now: datetime, *, error_message: str, retryable: bool) -> dict:
        return {
            "last_refresh_attempted_at": now,
            "next_refresh_retry_at": now + timedelta(minutes=5) if retryable else None,
            "last_refresh_error": error_message,
            "last_refresh_retryable": retryable,
            "refresh_status": "retryable_failure" if retryable else "failed",
            "last_refresh_outcome": "refresh_failed",
            "updated_at": now,
        }
