"""Monitoring service for tracked Copart lots."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Optional

from pymongo.database import Database

from cartrap.modules.copart_provider.models import CopartLotSnapshot
from cartrap.modules.copart_provider.service import CopartProvider
from cartrap.modules.monitoring.change_detection import detect_significant_changes
from cartrap.modules.monitoring.polling_policy import is_due_for_poll
from cartrap.modules.notifications.service import NotificationService
from cartrap.modules.watchlist.repository import WatchlistRepository
from cartrap.modules.watchlist.service import WatchlistService


class MonitoringService:
    def __init__(
        self,
        database: Database,
        provider_factory: Optional[Callable[[], CopartProvider]] = None,
        notification_service: Optional[NotificationService] = None,
    ) -> None:
        self.repository = WatchlistRepository(database)
        self.repository.ensure_indexes()
        self._provider_factory = provider_factory or CopartProvider
        self._notification_service = notification_service

    def poll_due_lots(self, now: datetime | None = None) -> dict:
        current_time = now or self._now()
        processed = 0
        updated = 0
        failed = 0
        events: list[dict] = []

        for tracked_lot in self.repository.list_active_tracked_lots():
            if not is_due_for_poll(tracked_lot, current_time):
                continue
            processed += 1
            try:
                event = self._poll_single_lot(tracked_lot, current_time)
            except Exception:
                failed += 1
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
            fresh_snapshot = provider.fetch_lot(tracked_lot["url"])
        finally:
            provider.close()

        latest_snapshot = self.repository.get_latest_snapshot_for_tracked_lot(str(tracked_lot["_id"]))
        next_snapshot = self._snapshot_document(tracked_lot, fresh_snapshot, now)
        changes = detect_significant_changes(latest_snapshot, next_snapshot)

        self.repository.update_tracked_lot_state(
            str(tracked_lot["_id"]),
            {
                **WatchlistService._tracked_lot_state_from_snapshot(fresh_snapshot),
                "last_checked_at": now,
            },
            updated_at=now,
        )

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
