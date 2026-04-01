"""Watchlist business logic."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
from typing import Callable, Optional

from fastapi import HTTPException, status
from pymongo.database import Database

from cartrap.modules.auction_domain.models import AuctionLotSnapshot, PROVIDER_COPART, build_lot_key, normalize_provider
from cartrap.modules.copart_provider.service import CopartProvider
from cartrap.modules.monitoring.change_detection import detect_significant_changes
from cartrap.modules.iaai_provider.service import IaaiProvider
from cartrap.modules.monitoring.polling_policy import DEFAULT_INTERVAL_MINUTES, get_poll_interval_minutes
from cartrap.modules.provider_connections.service import ProviderConnectionService
from cartrap.modules.system_status.service import SystemStatusService, build_freshness_envelope
from cartrap.modules.watchlist.repository import WatchlistRepository


logger = logging.getLogger(__name__)

DETAIL_FIELD_NAMES = (
    "odometer",
    "primary_damage",
    "estimated_retail_value",
    "has_key",
    "drivetrain",
    "highlights",
    "vin",
)


class WatchlistService:
    def __init__(
        self,
        database: Database,
        provider_factory: Optional[Callable[[], CopartProvider]] = None,
        provider_factories: Optional[dict[str, Callable[[], object]]] = None,
        default_poll_interval_minutes: int = DEFAULT_INTERVAL_MINUTES,
        provider_connection_service: ProviderConnectionService | None = None,
        system_status_service: SystemStatusService | None = None,
    ) -> None:
        self.repository = WatchlistRepository(database)
        self.repository.ensure_indexes()
        self._provider_factories: dict[str, Callable[[], object]] = {
            PROVIDER_COPART: provider_factory or CopartProvider,
            "iaai": IaaiProvider,
        }
        if provider_factories:
            self._provider_factories.update(provider_factories)
        self._default_poll_interval_minutes = default_poll_interval_minutes
        self._system_status_service = system_status_service or SystemStatusService(database)
        self._provider_connection_service = provider_connection_service

    def add_tracked_lot(
        self,
        owner_user: dict,
        lot_reference: str | None = None,
        *,
        provider: str = PROVIDER_COPART,
        provider_lot_id: str | None = None,
    ) -> dict:
        normalized_provider = normalize_provider(provider)
        snapshot, detail_etag = self._fetch_snapshot(
            normalized_provider,
            lot_reference or str(provider_lot_id or ""),
            owner_user_id=owner_user["id"],
        )
        existing = self.repository.find_tracked_lot_by_owner_and_lot_key(owner_user["id"], snapshot.lot_key)
        if existing is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Lot is already in watchlist.")

        now = self._now()
        tracked_lot = self.repository.create_tracked_lot(
            {
                "owner_user_id": owner_user["id"],
                "provider": snapshot.provider,
                "auction_label": snapshot.auction_label,
                "provider_lot_id": snapshot.provider_lot_id,
                "lot_key": snapshot.lot_key,
                "lot_number": snapshot.lot_number,
                "url": str(snapshot.url) if snapshot.url else None,
                "title": snapshot.title,
                **self._tracked_lot_state_from_snapshot(snapshot, detail_etag=detail_etag),
                "last_checked_at": now,
                "active": True,
                "created_at": now,
                "updated_at": now,
                "has_unseen_update": False,
                "latest_change_at": None,
                "latest_changes": {},
                "auction_reminder_sale_date": snapshot.sale_date,
                "auction_reminder_sent_minutes": [],
                "repair_requested_at": None,
                "last_refresh_attempted_at": now,
                "last_refresh_succeeded_at": now,
                "next_refresh_retry_at": None,
                "last_refresh_error": None,
                "last_refresh_retryable": False,
                "refresh_status": "idle",
            }
        )

        lot_snapshot = self.repository.create_snapshot(
            {
                "tracked_lot_id": str(tracked_lot["_id"]),
                "owner_user_id": owner_user["id"],
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
        )

        live_sync_status = self._system_status_service.get_live_sync_status()
        return {
            "tracked_lot": self.serialize_tracked_lot(tracked_lot, live_sync_status=live_sync_status),
            "initial_snapshot": self.serialize_snapshot(lot_snapshot),
        }

    def list_watchlist(self, owner_user: dict) -> dict:
        hydrated_items: list[dict] = []
        for item in self.repository.list_tracked_lots_for_owner(owner_user["id"]):
            hydrated_item = self._schedule_legacy_backfill(item)
            hydrated_items.append(hydrated_item)
        hydrated_items.sort(key=self._watchlist_sort_key)
        live_sync_status = self._system_status_service.get_live_sync_status()
        items = [self.serialize_tracked_lot(item, live_sync_status=live_sync_status) for item in hydrated_items]
        return {"items": items}

    def remove_tracked_lot(self, owner_user: dict, tracked_lot_id: str) -> None:
        tracked_lot = self.repository.find_tracked_lot_by_id_for_owner(tracked_lot_id, owner_user["id"])
        if tracked_lot is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tracked lot not found.")
        self.repository.delete_tracked_lot(tracked_lot_id)

    def refresh_tracked_lot_live(self, owner_user: dict, tracked_lot_id: str) -> dict:
        tracked_lot = self.repository.find_tracked_lot_by_id_for_owner(tracked_lot_id, owner_user["id"])
        if tracked_lot is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tracked lot not found.")

        now = self._now()
        try:
            snapshot, detail_etag = self._fetch_snapshot(
                tracked_lot.get("provider") or PROVIDER_COPART,
                tracked_lot.get("provider_lot_id") or tracked_lot.get("url") or tracked_lot["lot_number"],
                owner_user_id=owner_user["id"],
            )
        except HTTPException as exc:
            retryable, error_message = self.classify_refresh_exception(exc)
            self.repository.update_tracked_lot_state(
                tracked_lot_id,
                {
                    **self._build_refresh_failure_payload(now, error_message=error_message, retryable=retryable),
                    "last_refresh_priority_class": "manual",
                },
                updated_at=now,
            )
            raise

        next_snapshot = {
            "tracked_lot_id": tracked_lot_id,
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
        latest_snapshot = self.repository.get_latest_snapshot_for_tracked_lot(tracked_lot_id)
        changes = detect_significant_changes(latest_snapshot, next_snapshot)
        payload = {
            **self._tracked_lot_state_from_snapshot(snapshot, detail_etag=detail_etag),
            **self._build_refresh_success_payload(now),
            "last_refresh_priority_class": "manual",
            "last_refresh_change_count": len(changes),
            "last_refresh_reminder_count": 0,
            "last_checked_at": now,
            "repair_requested_at": None,
        }
        if changes:
            payload.update(
                {
                    "has_unseen_update": True,
                    "latest_change_at": now,
                    "latest_changes": changes,
                }
            )
            self.repository.create_snapshot(next_snapshot)
        self.repository.update_tracked_lot_state(tracked_lot_id, payload, updated_at=now)
        live_sync_status = self._system_status_service.get_live_sync_status()
        refreshed = self.repository.find_tracked_lot_by_id_for_owner(tracked_lot_id, owner_user["id"])
        if refreshed is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tracked lot not found.")
        return {"tracked_lot": self.serialize_tracked_lot(refreshed, live_sync_status=live_sync_status)}

    def acknowledge_tracked_lot_update(self, owner_user: dict, tracked_lot_id: str) -> dict:
        tracked_lot = self.repository.find_tracked_lot_by_id_for_owner(tracked_lot_id, owner_user["id"])
        if tracked_lot is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tracked lot not found.")

        acknowledged = tracked_lot
        if tracked_lot.get("has_unseen_update"):
            acknowledged = self.repository.acknowledge_tracked_lot_update(tracked_lot_id, self._now())
            if acknowledged is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tracked lot not found.")

        live_sync_status = self._system_status_service.get_live_sync_status()
        return {"tracked_lot": self.serialize_tracked_lot(acknowledged, live_sync_status=live_sync_status)}

    def get_tracked_lot_history(self, owner_user: dict, tracked_lot_id: str) -> dict:
        tracked_lot = self.repository.find_tracked_lot_by_id_for_owner(tracked_lot_id, owner_user["id"])
        if tracked_lot is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tracked lot not found.")

        snapshots = self.repository.list_snapshots_for_tracked_lot(tracked_lot_id)
        entries: list[dict] = []
        for index, snapshot in enumerate(snapshots[:-1]):
            previous_snapshot = snapshots[index + 1]
            changes = detect_significant_changes(previous_snapshot, snapshot)
            if not changes:
                continue
            entries.append(
                {
                    "snapshot": self.serialize_snapshot(snapshot),
                    "changes": changes,
                }
            )
        return {
            "tracked_lot_id": tracked_lot_id,
            "entries": entries,
        }

    def _fetch_snapshot(
        self,
        provider_name: str,
        lot_reference: str,
        owner_user_id: str | None = None,
    ) -> tuple[AuctionLotSnapshot, str | None]:
        provider = self._build_live_provider(owner_user_id, provider_name)
        try:
            if hasattr(provider, "fetch_lot_conditional"):
                result = provider.fetch_lot_conditional(lot_reference)
                if result.snapshot is None:
                    raise RuntimeError("Conditional lot fetch returned no snapshot.")
                return result.snapshot, result.etag
            return provider.fetch_lot(lot_reference), None
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("Lot fetch failed for provider=%s lot_reference=%s", provider_name, lot_reference)
            provider_label = "IAAI" if str(provider_name).lower() == "iaai" else "Copart"
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to fetch lot details from {provider_label}: {exc}",
            ) from exc
        finally:
            provider.close()

    def _schedule_legacy_backfill(self, tracked_lot: dict) -> dict:
        if not self.tracked_lot_needs_legacy_backfill(tracked_lot):
            return tracked_lot
        requested_at = tracked_lot.get("repair_requested_at")
        if requested_at is None:
            requested_at = self._now()
            self.repository.request_legacy_backfill(str(tracked_lot["_id"]), requested_at)
        return {
            **tracked_lot,
            "repair_requested_at": requested_at,
            "refresh_status": "repair_pending",
        }

    @staticmethod
    def tracked_lot_needs_legacy_backfill(tracked_lot: dict) -> bool:
        image_urls = list(tracked_lot.get("image_urls", []))
        needs_media_backfill = not tracked_lot.get("thumbnail_url") and not image_urls
        needs_detail_backfill = any(field_name not in tracked_lot for field_name in DETAIL_FIELD_NAMES)
        return needs_media_backfill or needs_detail_backfill

    @staticmethod
    def _tracked_lot_state_from_snapshot(snapshot: AuctionLotSnapshot, detail_etag: str | None = None) -> dict:
        payload = {
            "provider": snapshot.provider,
            "auction_label": snapshot.auction_label,
            "provider_lot_id": snapshot.provider_lot_id,
            "lot_key": snapshot.lot_key,
            "thumbnail_url": str(snapshot.thumbnail_url) if snapshot.thumbnail_url else None,
            "image_urls": [str(url) for url in snapshot.image_urls],
            "odometer": snapshot.odometer,
            "primary_damage": snapshot.primary_damage,
            "estimated_retail_value": snapshot.estimated_retail_value,
            "has_key": snapshot.has_key,
            "drivetrain": snapshot.drivetrain,
            "highlights": list(snapshot.highlights),
            "vin": snapshot.vin,
            "status": snapshot.status,
            "raw_status": snapshot.raw_status,
            "sale_date": snapshot.sale_date,
            "current_bid": snapshot.current_bid,
            "buy_now_price": snapshot.buy_now_price,
            "currency": snapshot.currency,
        }
        if detail_etag is not None:
            payload["detail_etag"] = detail_etag
        return payload

    @staticmethod
    def _watchlist_sort_key(tracked_lot: dict) -> tuple[int, float, float, str]:
        sale_date = tracked_lot.get("sale_date")
        created_at = tracked_lot.get("created_at")
        sale_timestamp = sale_date.timestamp() if isinstance(sale_date, datetime) else float("inf")
        created_timestamp = created_at.timestamp() if isinstance(created_at, datetime) else float("inf")
        return (0 if sale_date is not None else 1, sale_timestamp, created_timestamp, str(tracked_lot.get("lot_number", "")))

    def serialize_tracked_lot(self, document: dict, live_sync_status: dict | None = None) -> dict:
        current_time = self._now()
        freshness = build_freshness_envelope(
            last_synced_at=document.get("last_checked_at"),
            stale_after_window=timedelta(
                minutes=get_poll_interval_minutes(
                    document,
                    current_time,
                    default_interval_minutes=self._default_poll_interval_minutes,
                )
            ),
            live_sync_status=live_sync_status,
            current_time=current_time,
        )
        return {
            "id": str(document["_id"]),
            "provider": document.get("provider") or PROVIDER_COPART,
            "auction_label": document.get("auction_label") or ("IAAI" if document.get("provider") == "iaai" else "Copart"),
            "provider_lot_id": document.get("provider_lot_id") or document["lot_number"],
            "lot_key": document.get("lot_key")
            or build_lot_key(document.get("provider") or PROVIDER_COPART, document.get("provider_lot_id"), document["lot_number"]),
            "lot_number": document["lot_number"],
            "url": document["url"],
            "title": document["title"],
            "thumbnail_url": document.get("thumbnail_url"),
            "image_urls": list(document.get("image_urls", [])),
            "odometer": document.get("odometer"),
            "primary_damage": document.get("primary_damage"),
            "estimated_retail_value": document.get("estimated_retail_value"),
            "has_key": document.get("has_key"),
            "drivetrain": document.get("drivetrain"),
            "highlights": list(document.get("highlights", [])),
            "vin": document.get("vin"),
            "status": document["status"],
            "raw_status": document["raw_status"],
            "current_bid": document.get("current_bid"),
            "buy_now_price": document.get("buy_now_price"),
            "currency": document["currency"],
            "sale_date": document.get("sale_date"),
            "last_checked_at": document["last_checked_at"],
            "freshness": freshness,
            "refresh_state": self.serialize_refresh_state(document),
            "connection_diagnostic": self._get_connection_diagnostic(
                document.get("owner_user_id"),
                provider=document.get("provider") or PROVIDER_COPART,
            ),
            "created_at": document["created_at"],
            "has_unseen_update": document.get("has_unseen_update", False),
            "latest_change_at": document.get("latest_change_at"),
            "latest_changes": document.get("latest_changes", {}),
        }

    @staticmethod
    def serialize_snapshot(document: dict) -> dict:
        return {
            "id": str(document["_id"]),
            "tracked_lot_id": document["tracked_lot_id"],
            "provider": document.get("provider") or PROVIDER_COPART,
            "provider_lot_id": document.get("provider_lot_id") or document["lot_number"],
            "lot_key": document.get("lot_key")
            or build_lot_key(document.get("provider") or PROVIDER_COPART, document.get("provider_lot_id"), document["lot_number"]),
            "lot_number": document["lot_number"],
            "status": document["status"],
            "raw_status": document["raw_status"],
            "current_bid": document.get("current_bid"),
            "buy_now_price": document.get("buy_now_price"),
            "currency": document["currency"],
            "sale_date": document.get("sale_date"),
            "detected_at": document["detected_at"],
        }

    @staticmethod
    def serialize_refresh_state(document: dict) -> dict:
        status = document.get("refresh_status") or "idle"
        if status == "idle" and document.get("repair_requested_at") is not None:
            status = "repair_pending"
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
                "change_count": int(document.get("last_refresh_change_count") or 0),
                "reminder_count": int(document.get("last_refresh_reminder_count") or 0),
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
            "last_refresh_change_count": 0,
            "last_refresh_reminder_count": 0,
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
        }

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def _build_live_provider(self, owner_user_id: str | None, provider: str = PROVIDER_COPART):
        if self._provider_connection_service is not None and owner_user_id is not None:
            return self._provider_connection_service.build_provider_for_owner(owner_user_id, provider=provider)
        return self._provider_factories[provider]()

    def _get_connection_diagnostic(self, owner_user_id: str | None, provider: str = PROVIDER_COPART) -> dict | None:
        if self._provider_connection_service is None or not owner_user_id:
            return None
        return self._provider_connection_service.get_connection_diagnostic(owner_user_id, provider=provider)
