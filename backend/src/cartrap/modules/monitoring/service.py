"""Monitoring service for tracked Copart lots."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from time import perf_counter
from typing import Callable, Optional

from fastapi import HTTPException
from pymongo.database import Database

from cartrap.core.logging import make_log_extra, new_correlation_id
from cartrap.modules.auction_domain.models import AuctionLotSnapshot, PROVIDER_COPART, build_lot_key
from cartrap.modules.copart_provider.service import CopartProvider
from cartrap.modules.iaai_provider.service import IaaiProvider
from cartrap.modules.monitoring.change_detection import detect_significant_changes
from cartrap.modules.monitoring.job_runtime import JobRuntimeService
from cartrap.modules.monitoring.polling_policy import (
    build_priority_sort_key,
    DEFAULT_INTERVAL_MINUTES,
    NEAR_AUCTION_INTERVAL_MINUTES,
    NEAR_AUCTION_WINDOW_MINUTES,
    get_priority_class,
    is_due_for_poll,
)
from cartrap.modules.notifications.service import NotificationService
from cartrap.modules.provider_connections.service import ProviderConnectionService
from cartrap.modules.system_status.service import SystemStatusService
from cartrap.modules.watchlist.repository import WatchlistRepository
from cartrap.modules.watchlist.service import WatchlistService


logger = logging.getLogger(__name__)


class MonitoringService:
    AUCTION_REMINDER_OFFSETS_MINUTES = (60, 15, 0)

    def __init__(
        self,
        database: Database,
        provider_factory: Optional[Callable[[], CopartProvider]] = None,
        provider_factories: Optional[dict[str, Callable[[], object]]] = None,
        notification_service: Optional[NotificationService] = None,
        default_poll_interval_minutes: int = DEFAULT_INTERVAL_MINUTES,
        near_auction_poll_interval_minutes: int = NEAR_AUCTION_INTERVAL_MINUTES,
        near_auction_window_minutes: int = NEAR_AUCTION_WINDOW_MINUTES,
        refresh_job_runtime: JobRuntimeService | None = None,
        provider_connection_service: ProviderConnectionService | None = None,
    ) -> None:
        self.repository = WatchlistRepository(database)
        self.repository.ensure_indexes()
        self._provider_factories: dict[str, Callable[[], object]] = {
            PROVIDER_COPART: provider_factory or CopartProvider,
            "iaai": IaaiProvider,
        }
        if provider_factories:
            self._provider_factories.update(provider_factories)
        self._notification_service = notification_service
        self._system_status_service = SystemStatusService(database)
        self._default_poll_interval_minutes = default_poll_interval_minutes
        self._near_auction_poll_interval_minutes = near_auction_poll_interval_minutes
        self._near_auction_window_minutes = near_auction_window_minutes
        self._refresh_job_runtime = refresh_job_runtime or JobRuntimeService(database)
        self._provider_connection_service = provider_connection_service

    def poll_due_lots(self, now: datetime | None = None) -> dict:
        current_time = now or self._now()
        processed = 0
        updated = 0
        failed = 0
        skipped = 0
        events: list[dict] = []
        reminder_events: list[dict] = []
        jobs: list[dict] = []

        due_tracked_lots: list[dict] = []
        for tracked_lot in self.repository.list_active_tracked_lots():
            if not self._should_poll_tracked_lot(tracked_lot, current_time):
                continue
            due_tracked_lots.append(tracked_lot)

        due_tracked_lots.sort(
            key=lambda item: build_priority_sort_key(
                item,
                current_time,
                near_auction_window_minutes=self._near_auction_window_minutes,
            )
        )

        for tracked_lot in due_tracked_lots:
            tracked_lot_id = str(tracked_lot["_id"])
            priority_class = get_priority_class(
                tracked_lot,
                current_time,
                near_auction_window_minutes=self._near_auction_window_minutes,
            )
            correlation_id = new_correlation_id("watchlist-poll")
            started_at = perf_counter()
            runtime = self._refresh_job_runtime.acquire(
                job_type="watchlist_poll",
                resource_id=tracked_lot_id,
                now=current_time,
                metadata={
                    "owner_user_id": tracked_lot["owner_user_id"],
                    "lot_number": tracked_lot["lot_number"],
                    "priority_class": priority_class,
                },
            )
            if runtime is None:
                skipped += 1
                jobs.append(
                    self._refresh_job_runtime.describe_skip(
                        job_type="watchlist_poll",
                        resource_id=tracked_lot_id,
                        now=current_time,
                    )
                )
                continue

            diagnostic = self._get_connection_diagnostic(
                tracked_lot["owner_user_id"],
                provider=tracked_lot.get("provider") or PROVIDER_COPART,
            )
            if diagnostic is not None and diagnostic["status"] != "ready":
                skipped += 1
                self.repository.update_tracked_lot_state(
                    tracked_lot_id,
                    {
                        **WatchlistService._build_refresh_failure_payload(
                            current_time,
                            error_message=diagnostic["message"],
                            retryable=False,
                        ),
                        "last_refresh_priority_class": priority_class,
                    },
                    updated_at=current_time,
                )
                jobs.append(
                    self._refresh_job_runtime.fail_non_retryable(
                        runtime,
                        now=current_time,
                        outcome=diagnostic["status"],
                        error_message=diagnostic["message"],
                        metadata={
                            "owner_user_id": tracked_lot["owner_user_id"],
                            "lot_number": tracked_lot["lot_number"],
                            "priority_class": priority_class,
                        },
                    )
                )
                continue

            processed += 1
            last_checked_at = tracked_lot.get("last_checked_at")
            stale_for_seconds = (
                round((current_time - last_checked_at).total_seconds(), 2) if isinstance(last_checked_at, datetime) else None
            )
            logger.info(
                "watchlist.refresh.start",
                extra=make_log_extra(
                    "watchlist.refresh.start",
                    correlation_id=correlation_id,
                    tracked_lot_id=tracked_lot_id,
                    owner_user_id=tracked_lot["owner_user_id"],
                    lot_number=tracked_lot["lot_number"],
                    priority_class=priority_class,
                    stale_for_seconds=stale_for_seconds,
                    attempt_count=runtime.get("attempt_count"),
                ),
            )
            try:
                poll_result = self._poll_single_lot(tracked_lot, current_time)
            except Exception as exc:
                failed += 1
                self._system_status_service.mark_live_sync_degraded("watchlist_poll", exc, checked_at=current_time)
                retryable = True
                error_message = str(exc).strip() or "Watchlist refresh failed."
                if isinstance(exc, HTTPException):
                    retryable, error_message = WatchlistService.classify_refresh_exception(exc)
                self.repository.update_tracked_lot_state(
                    tracked_lot_id,
                    {
                        **WatchlistService._build_refresh_failure_payload(
                            current_time,
                            error_message=error_message,
                            retryable=retryable,
                        ),
                        "last_refresh_priority_class": priority_class,
                    },
                    updated_at=current_time,
                )
                jobs.append(
                    (
                        self._refresh_job_runtime.fail_retryable(
                            runtime,
                            now=current_time,
                            outcome="refresh_failed",
                            error_message=error_message,
                            metadata={
                                "owner_user_id": tracked_lot["owner_user_id"],
                                "lot_number": tracked_lot["lot_number"],
                                "priority_class": priority_class,
                            },
                        )
                        if retryable
                        else self._refresh_job_runtime.fail_non_retryable(
                            runtime,
                            now=current_time,
                            outcome="refresh_failed",
                            error_message=error_message,
                            metadata={
                                "owner_user_id": tracked_lot["owner_user_id"],
                                "lot_number": tracked_lot["lot_number"],
                                "priority_class": priority_class,
                            },
                        )
                    )
                )
                logger.exception(
                    "watchlist.refresh.failed",
                    extra=make_log_extra(
                        "watchlist.refresh.failed",
                        correlation_id=correlation_id,
                        tracked_lot_id=tracked_lot_id,
                        owner_user_id=tracked_lot["owner_user_id"],
                        lot_number=tracked_lot["lot_number"],
                        priority_class=priority_class,
                        duration_ms=round((perf_counter() - started_at) * 1000, 2),
                        retryable=retryable,
                        error_message=error_message,
                    ),
                )
                continue

            event = poll_result["change_event"]
            if event is not None:
                updated += 1
                events.append(event)
                if self._notification_service is not None:
                    self._notification_service.send_lot_change_notification(event)
            reminder_batch = poll_result["reminder_events"]
            if reminder_batch:
                reminder_events.extend(reminder_batch)
                if self._notification_service is not None:
                    for reminder_event in reminder_batch:
                        self._notification_service.send_auction_reminder_notification(reminder_event)
            jobs.append(
                self._refresh_job_runtime.complete(
                    runtime,
                    now=current_time,
                    outcome="refreshed" if event is not None or reminder_batch else "not_modified",
                    metadata={
                        "owner_user_id": tracked_lot["owner_user_id"],
                        "lot_number": tracked_lot["lot_number"],
                        "priority_class": priority_class,
                        "updated": event is not None,
                        "reminders_sent": len(reminder_batch),
                    },
                )
            )
            logger.info(
                "watchlist.refresh.success",
                extra=make_log_extra(
                    "watchlist.refresh.success",
                    correlation_id=correlation_id,
                    tracked_lot_id=tracked_lot_id,
                    owner_user_id=tracked_lot["owner_user_id"],
                    lot_number=tracked_lot["lot_number"],
                    priority_class=priority_class,
                    duration_ms=round((perf_counter() - started_at) * 1000, 2),
                    outcome="refreshed" if event is not None or reminder_batch else "not_modified",
                    change_count=len(event["changes"]) if event is not None else 0,
                    reminder_count=len(reminder_batch),
                ),
            )

        return {
            "processed": processed,
            "updated": updated,
            "failed": failed,
            "skipped": skipped,
            "events": events,
            "reminded": len(reminder_events),
            "reminder_events": reminder_events,
            "jobs": jobs,
        }

    def _should_poll_tracked_lot(self, tracked_lot: dict, now: datetime) -> bool:
        repair_requested_at = self._normalize_datetime(tracked_lot.get("repair_requested_at"))
        last_checked_at = self._normalize_datetime(tracked_lot.get("last_checked_at"))
        if repair_requested_at is not None and (last_checked_at is None or repair_requested_at > last_checked_at):
            return True
        if is_due_for_poll(
            tracked_lot,
            now,
            default_interval_minutes=self._default_poll_interval_minutes,
            near_auction_interval_minutes=self._near_auction_poll_interval_minutes,
            near_auction_window_minutes=self._near_auction_window_minutes,
        ):
            return True
        return self._crossed_pending_auction_reminder_threshold(tracked_lot, now)

    def _poll_single_lot(self, tracked_lot: dict, now: datetime) -> dict:
        provider = self._build_live_provider(
            tracked_lot["owner_user_id"],
            provider=tracked_lot.get("provider") or PROVIDER_COPART,
        )
        priority_class = get_priority_class(
            tracked_lot,
            now,
            near_auction_window_minutes=self._near_auction_window_minutes,
        )
        try:
            fetch_reference = self._build_detail_fetch_reference(tracked_lot)
            if hasattr(provider, "fetch_lot_conditional"):
                fetch_result = provider.fetch_lot_conditional(
                    fetch_reference,
                    etag=tracked_lot.get("detail_etag"),
                )
            else:
                fetch_result = None
                fresh_snapshot = provider.fetch_lot(fetch_reference)
        finally:
            provider.close()

        if fetch_result is not None and fetch_result.not_modified:
            reminder_events, reminder_state_payload = self._build_auction_reminders(
                tracked_lot,
                sale_date=tracked_lot.get("sale_date"),
                now=now,
                title=tracked_lot.get("title"),
            )
            payload = {
                "last_checked_at": now,
                **WatchlistService._build_refresh_success_payload(now),
                "last_refresh_priority_class": priority_class,
                "last_refresh_outcome": "not_modified",
                "repair_requested_at": None,
                "last_refresh_change_count": 0,
                "last_refresh_reminder_count": len(reminder_events),
                **reminder_state_payload,
            }
            if fetch_result.etag is not None:
                payload["detail_etag"] = fetch_result.etag
            self.repository.update_tracked_lot_state(str(tracked_lot["_id"]), payload, updated_at=now)
            self._system_status_service.mark_live_sync_available("watchlist_poll", checked_at=now)
            return {
                "change_event": None,
                "reminder_events": reminder_events,
            }

        if fetch_result is not None:
            fresh_snapshot = fetch_result.snapshot
            detail_etag = fetch_result.etag
        else:
            detail_etag = None

        if fresh_snapshot is None:
            raise RuntimeError("Conditional lot fetch returned no snapshot.")

        latest_snapshot = self.repository.get_latest_snapshot_for_tracked_lot(str(tracked_lot["_id"]))
        next_snapshot = self._snapshot_document(tracked_lot, fresh_snapshot, now)
        changes = detect_significant_changes(latest_snapshot, next_snapshot)
        reminder_events, reminder_state_payload = self._build_auction_reminders(
            tracked_lot,
            sale_date=fresh_snapshot.sale_date,
            now=now,
            title=fresh_snapshot.title,
        )

        tracked_lot_payload = {
            **WatchlistService._tracked_lot_state_from_snapshot(fresh_snapshot, detail_etag=detail_etag),
            "last_checked_at": now,
            **WatchlistService._build_refresh_success_payload(now),
            "last_refresh_priority_class": priority_class,
            "last_refresh_outcome": "refreshed" if changes else "not_modified",
            "repair_requested_at": None,
            "last_refresh_change_count": len(changes),
            "last_refresh_reminder_count": len(reminder_events),
            **reminder_state_payload,
        }
        if changes:
            tracked_lot_payload.update(
                {
                    "has_unseen_update": True,
                    "latest_change_at": now,
                    "latest_changes": changes,
                }
            )
        self.repository.update_tracked_lot_state(str(tracked_lot["_id"]), tracked_lot_payload, updated_at=now)
        self._system_status_service.mark_live_sync_available("watchlist_poll", checked_at=now)

        if not changes:
            return {
                "change_event": None,
                "reminder_events": reminder_events,
            }

        stored_snapshot = self.repository.create_snapshot(next_snapshot)
        return {
            "change_event": {
                "tracked_lot_id": str(tracked_lot["_id"]),
                "snapshot_id": str(stored_snapshot["_id"]),
                "owner_user_id": tracked_lot["owner_user_id"],
                "provider": tracked_lot.get("provider") or PROVIDER_COPART,
                "provider_lot_id": tracked_lot.get("provider_lot_id") or tracked_lot["lot_number"],
                "lot_key": tracked_lot.get("lot_key")
                or build_lot_key(tracked_lot.get("provider") or PROVIDER_COPART, tracked_lot.get("provider_lot_id"), tracked_lot["lot_number"]),
                "lot_number": tracked_lot["lot_number"],
                "title": fresh_snapshot.title,
                "currency": fresh_snapshot.currency,
                "changes": changes,
            },
            "reminder_events": reminder_events,
        }

    @staticmethod
    def _build_detail_fetch_reference(tracked_lot: dict) -> str:
        provider = str(tracked_lot.get("provider") or PROVIDER_COPART).strip().lower()
        if provider == PROVIDER_COPART and tracked_lot.get("url"):
            return str(tracked_lot["url"])
        return str(tracked_lot.get("provider_lot_id") or tracked_lot.get("url") or tracked_lot["lot_number"])

    def _build_live_provider(self, owner_user_id: str | None, provider: str = PROVIDER_COPART):
        if self._provider_connection_service is not None and owner_user_id is not None:
            return self._provider_connection_service.build_provider_for_owner(owner_user_id, provider=provider)
        return self._provider_factories[provider]()

    def _get_connection_diagnostic(self, owner_user_id: str | None, provider: str = PROVIDER_COPART) -> dict | None:
        if self._provider_connection_service is None or not owner_user_id:
            return None
        return self._provider_connection_service.get_connection_diagnostic(owner_user_id, provider=provider)

    def _build_auction_reminders(
        self,
        tracked_lot: dict,
        *,
        sale_date: datetime | None,
        now: datetime,
        title: str | None,
    ) -> tuple[list[dict], dict]:
        normalized_sale_date = self._normalize_datetime(sale_date)
        stored_sale_date = self._normalize_datetime(tracked_lot.get("auction_reminder_sale_date"))
        sent_minutes = self._normalize_sent_minutes(tracked_lot.get("auction_reminder_sent_minutes"))

        if normalized_sale_date is None:
            return [], {
                "auction_reminder_sale_date": None,
                "auction_reminder_sent_minutes": [],
            }

        if stored_sale_date != normalized_sale_date:
            sent_minutes = set()

        due_offsets: list[int] = []
        for offset_minutes in self.AUCTION_REMINDER_OFFSETS_MINUTES:
            if offset_minutes in sent_minutes:
                continue
            if self._is_auction_reminder_due(normalized_sale_date, now, offset_minutes):
                due_offsets.append(offset_minutes)
                sent_minutes.add(offset_minutes)

        reminder_events = [
            {
                "tracked_lot_id": str(tracked_lot["_id"]),
                "owner_user_id": tracked_lot["owner_user_id"],
                "lot_number": tracked_lot["lot_number"],
                "title": title or tracked_lot.get("title") or tracked_lot["lot_number"],
                "sale_date": normalized_sale_date,
                "reminder_offset_minutes": offset_minutes,
            }
            for offset_minutes in due_offsets
        ]

        reminder_state_payload = {
            "auction_reminder_sale_date": normalized_sale_date,
            "auction_reminder_sent_minutes": [
                offset_minutes for offset_minutes in self.AUCTION_REMINDER_OFFSETS_MINUTES if offset_minutes in sent_minutes
            ],
        }
        return reminder_events, reminder_state_payload

    def _crossed_pending_auction_reminder_threshold(self, tracked_lot: dict, now: datetime) -> bool:
        sale_date = self._normalize_datetime(tracked_lot.get("sale_date"))
        last_checked_at = self._normalize_datetime(tracked_lot.get("last_checked_at"))
        if sale_date is None or last_checked_at is None:
            return False

        stored_sale_date = self._normalize_datetime(tracked_lot.get("auction_reminder_sale_date"))
        sent_minutes = self._normalize_sent_minutes(tracked_lot.get("auction_reminder_sent_minutes"))
        if stored_sale_date != sale_date:
            sent_minutes = set()

        for offset_minutes in self.AUCTION_REMINDER_OFFSETS_MINUTES:
            if offset_minutes in sent_minutes:
                continue
            trigger_at = sale_date - timedelta(minutes=offset_minutes)
            if offset_minutes > 0 and now >= sale_date:
                continue
            if last_checked_at < trigger_at <= now:
                return True
        return False

    @staticmethod
    def _normalize_datetime(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    @staticmethod
    def _normalize_sent_minutes(value: object) -> set[int]:
        normalized: set[int] = set()
        if not isinstance(value, list):
            return normalized
        for item in value:
            try:
                normalized.add(int(item))
            except (TypeError, ValueError):
                continue
        return normalized

    @staticmethod
    def _is_auction_reminder_due(sale_date: datetime, now: datetime, offset_minutes: int) -> bool:
        if offset_minutes == 0:
            return now >= sale_date
        threshold = sale_date - timedelta(minutes=offset_minutes)
        return threshold <= now < sale_date

    @staticmethod
    def _snapshot_document(tracked_lot: dict, snapshot: AuctionLotSnapshot, now: datetime) -> dict:
        return {
            "tracked_lot_id": str(tracked_lot["_id"]),
            "owner_user_id": tracked_lot["owner_user_id"],
            "provider": snapshot.provider,
            "provider_lot_id": snapshot.provider_lot_id,
            "lot_key": snapshot.lot_key,
            "lot_number": snapshot.lot_number,
            "status": snapshot.status,
            "raw_status": snapshot.raw_status,
            "sale_date": snapshot.sale_date,
            "current_bid": snapshot.current_bid,
            "buy_now_price": snapshot.buy_now_price,
            "currency": snapshot.currency,
            "detected_at": now,
        }

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)
