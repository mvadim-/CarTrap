"""Monitoring service for tracked Copart lots."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

from pymongo.database import Database

from cartrap.modules.copart_provider.models import CopartLotSnapshot
from cartrap.modules.copart_provider.service import CopartProvider
from cartrap.modules.monitoring.change_detection import detect_significant_changes
from cartrap.modules.monitoring.polling_policy import (
    DEFAULT_INTERVAL_MINUTES,
    NEAR_AUCTION_INTERVAL_MINUTES,
    NEAR_AUCTION_WINDOW_MINUTES,
    is_due_for_poll,
)
from cartrap.modules.notifications.service import NotificationService
from cartrap.modules.system_status.service import SystemStatusService
from cartrap.modules.watchlist.repository import WatchlistRepository
from cartrap.modules.watchlist.service import WatchlistService


class MonitoringService:
    AUCTION_REMINDER_OFFSETS_MINUTES = (60, 15, 0)

    def __init__(
        self,
        database: Database,
        provider_factory: Optional[Callable[[], CopartProvider]] = None,
        notification_service: Optional[NotificationService] = None,
        default_poll_interval_minutes: int = DEFAULT_INTERVAL_MINUTES,
        near_auction_poll_interval_minutes: int = NEAR_AUCTION_INTERVAL_MINUTES,
        near_auction_window_minutes: int = NEAR_AUCTION_WINDOW_MINUTES,
    ) -> None:
        self.repository = WatchlistRepository(database)
        self.repository.ensure_indexes()
        self._provider_factory = provider_factory or CopartProvider
        self._notification_service = notification_service
        self._system_status_service = SystemStatusService(database)
        self._default_poll_interval_minutes = default_poll_interval_minutes
        self._near_auction_poll_interval_minutes = near_auction_poll_interval_minutes
        self._near_auction_window_minutes = near_auction_window_minutes

    def poll_due_lots(self, now: datetime | None = None) -> dict:
        current_time = now or self._now()
        processed = 0
        updated = 0
        failed = 0
        events: list[dict] = []
        reminder_events: list[dict] = []

        for tracked_lot in self.repository.list_active_tracked_lots():
            if not self._should_poll_tracked_lot(tracked_lot, current_time):
                continue
            processed += 1
            try:
                poll_result = self._poll_single_lot(tracked_lot, current_time)
            except Exception as exc:
                failed += 1
                self._system_status_service.mark_live_sync_degraded("watchlist_poll", exc, checked_at=current_time)
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

        return {
            "processed": processed,
            "updated": updated,
            "failed": failed,
            "events": events,
            "reminded": len(reminder_events),
            "reminder_events": reminder_events,
        }

    def _should_poll_tracked_lot(self, tracked_lot: dict, now: datetime) -> bool:
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
            reminder_events, reminder_state_payload = self._build_auction_reminders(
                tracked_lot,
                sale_date=tracked_lot.get("sale_date"),
                now=now,
                title=tracked_lot.get("title"),
            )
            payload = {
                "last_checked_at": now,
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
                "lot_number": tracked_lot["lot_number"],
                "title": fresh_snapshot.title,
                "currency": fresh_snapshot.currency,
                "changes": changes,
            },
            "reminder_events": reminder_events,
        }

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
