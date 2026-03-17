"""Monitoring service for tracked Copart lots."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Optional

from pymongo.database import Database

from cartrap.modules.copart_provider.models import CopartLotSnapshot
from cartrap.modules.copart_provider.service import CopartProvider
from cartrap.modules.monitoring.change_detection import detect_significant_changes
from cartrap.modules.monitoring.polling_policy import (
    DEFAULT_INTERVAL_MINUTES,
    NEAR_AUCTION_INTERVAL_MINUTES,
    NEAR_AUCTION_WINDOW_HOURS,
    is_due_for_poll,
)
from cartrap.modules.notifications.service import NotificationService
from cartrap.modules.system_status.service import SystemStatusService
from cartrap.modules.watchlist.repository import WatchlistRepository
from cartrap.modules.watchlist.service import WatchlistService


class MonitoringService:
    def __init__(
        self,
        database: Database,
        provider_factory: Optional[Callable[[], CopartProvider]] = None,
        notification_service: Optional[NotificationService] = None,
        default_poll_interval_minutes: int = DEFAULT_INTERVAL_MINUTES,
        near_auction_poll_interval_minutes: int = NEAR_AUCTION_INTERVAL_MINUTES,
        near_auction_window_hours: int = NEAR_AUCTION_WINDOW_HOURS,
    ) -> None:
        self.repository = WatchlistRepository(database)
        self.repository.ensure_indexes()
        self._provider_factory = provider_factory or CopartProvider
        self._notification_service = notification_service
        self._system_status_service = SystemStatusService(database)
        self._default_poll_interval_minutes = default_poll_interval_minutes
        self._near_auction_poll_interval_minutes = near_auction_poll_interval_minutes
        self._near_auction_window_hours = near_auction_window_hours

    def poll_due_lots(self, now: datetime | None = None) -> dict:
        current_time = now or self._now()
        processed = 0
        updated = 0
        failed = 0
        events: list[dict] = []

        for tracked_lot in self.repository.list_active_tracked_lots():
            if not is_due_for_poll(
                tracked_lot,
                current_time,
                default_interval_minutes=self._default_poll_interval_minutes,
                near_auction_interval_minutes=self._near_auction_poll_interval_minutes,
                near_auction_window_hours=self._near_auction_window_hours,
            ):
                continue
            processed += 1
            try:
                event = self._poll_single_lot(tracked_lot, current_time)
            except Exception as exc:
                failed += 1
                self._system_status_service.mark_live_sync_degraded("watchlist_poll", exc, checked_at=current_time)
                continue

            if event is not None:
                updated += 1
                events.append(event)
                if self._notification_service is not None:
                    self._notification_service.send_lot_change_notification(event)

        return {
            "processed": processed,
            "updated": updated,
            "failed": failed,
            "events": events,
        }

    def _poll_single_lot(self, tracked_lot: dict, now: datetime) -> dict | None:
        provider = self._provider_factory()
        try:
            if hasattr(provider, "fetch_lot_conditional"):
                fetch_result = provider.fetch_lot_conditional(tracked_lot["url"], etag=tracked_lot.get("detail_etag"))
            else:
                fetch_result = None
                fresh_snapshot = provider.fetch_lot(tracked_lot["url"])
        finally:
            provider.close()

        if fetch_result is not None and fetch_result.not_modified:
            payload = {"last_checked_at": now}
            if fetch_result.etag is not None:
                payload["detail_etag"] = fetch_result.etag
            self.repository.update_tracked_lot_state(str(tracked_lot["_id"]), payload, updated_at=now)
            self._system_status_service.mark_live_sync_available("watchlist_poll", checked_at=now)
            return None

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

        self.repository.update_tracked_lot_state(
            str(tracked_lot["_id"]),
            {
                **WatchlistService._tracked_lot_state_from_snapshot(fresh_snapshot, detail_etag=detail_etag),
                "last_checked_at": now,
            },
            updated_at=now,
        )
        self._system_status_service.mark_live_sync_available("watchlist_poll", checked_at=now)

        if not changes:
            return None

        stored_snapshot = self.repository.create_snapshot(next_snapshot)
        return {
            "tracked_lot_id": str(tracked_lot["_id"]),
            "snapshot_id": str(stored_snapshot["_id"]),
            "owner_user_id": tracked_lot["owner_user_id"],
            "lot_number": tracked_lot["lot_number"],
            "changes": changes,
        }

    @staticmethod
    def _snapshot_document(tracked_lot: dict, snapshot: CopartLotSnapshot, now: datetime) -> dict:
        return {
            "tracked_lot_id": str(tracked_lot["_id"]),
            "owner_user_id": tracked_lot["owner_user_id"],
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
