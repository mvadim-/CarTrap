"""Watchlist business logic."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Callable, Optional

from fastapi import HTTPException, status
from pymongo.database import Database

from cartrap.modules.copart_provider.models import CopartLotSnapshot
from cartrap.modules.copart_provider.service import CopartProvider
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
    ) -> None:
        self.repository = WatchlistRepository(database)
        self.repository.ensure_indexes()
        self._provider_factory = provider_factory or CopartProvider

    def add_tracked_lot(self, owner_user: dict, lot_url: str) -> dict:
        snapshot, detail_etag = self._fetch_snapshot(lot_url)
        existing = self.repository.find_tracked_lot_by_owner_and_lot_number(owner_user["id"], snapshot.lot_number)
        if existing is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Lot is already in watchlist.")

        now = self._now()
        tracked_lot = self.repository.create_tracked_lot(
            {
                "owner_user_id": owner_user["id"],
                "lot_number": snapshot.lot_number,
                "url": str(snapshot.url),
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
            }
        )

        lot_snapshot = self.repository.create_snapshot(
            {
                "tracked_lot_id": str(tracked_lot["_id"]),
                "owner_user_id": owner_user["id"],
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

        return {
            "tracked_lot": self.serialize_tracked_lot(tracked_lot),
            "initial_snapshot": self.serialize_snapshot(lot_snapshot),
        }

    def list_watchlist(self, owner_user: dict) -> dict:
        unseen_update_ids: list[str] = []
        hydrated_items: list[dict] = []
        for item in self.repository.list_tracked_lots_for_owner(owner_user["id"]):
            hydrated_item = self._ensure_tracked_lot_fields(item)
            if hydrated_item.get("has_unseen_update"):
                unseen_update_ids.append(str(hydrated_item["_id"]))
            hydrated_items.append(hydrated_item)
        hydrated_items.sort(key=self._watchlist_sort_key)
        items = [self.serialize_tracked_lot(item) for item in hydrated_items]
        if unseen_update_ids:
            self.repository.clear_unseen_updates(unseen_update_ids)
        return {"items": items}

    def remove_tracked_lot(self, owner_user: dict, tracked_lot_id: str) -> None:
        tracked_lot = self.repository.find_tracked_lot_by_id_for_owner(tracked_lot_id, owner_user["id"])
        if tracked_lot is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tracked lot not found.")
        self.repository.delete_tracked_lot(tracked_lot_id)

    def _fetch_snapshot(self, lot_url: str) -> tuple[CopartLotSnapshot, str | None]:
        provider = self._provider_factory()
        try:
            if hasattr(provider, "fetch_lot_conditional"):
                result = provider.fetch_lot_conditional(lot_url)
                if result.snapshot is None:
                    raise RuntimeError("Conditional lot fetch returned no snapshot.")
                return result.snapshot, result.etag
            return provider.fetch_lot(lot_url), None
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("Copart lot fetch failed for lot_url=%s", lot_url)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to fetch lot details from Copart: {exc}",
            ) from exc
        finally:
            provider.close()

    def _ensure_tracked_lot_fields(self, tracked_lot: dict) -> dict:
        image_urls = list(tracked_lot.get("image_urls", []))
        needs_media_backfill = not tracked_lot.get("thumbnail_url") and not image_urls
        needs_detail_backfill = any(field_name not in tracked_lot for field_name in DETAIL_FIELD_NAMES)
        if not needs_media_backfill and not needs_detail_backfill:
            return tracked_lot

        try:
            snapshot, detail_etag = self._fetch_snapshot(tracked_lot["url"])
        except HTTPException:
            logger.warning("Skipping watchlist state backfill for tracked_lot_id=%s", tracked_lot.get("_id"))
            return tracked_lot

        payload = self._tracked_lot_state_from_snapshot(snapshot, detail_etag=detail_etag)
        if not needs_media_backfill:
            payload.pop("thumbnail_url", None)
            payload.pop("image_urls", None)
        if not needs_detail_backfill:
            for field_name in DETAIL_FIELD_NAMES:
                payload.pop(field_name, None)

        if not payload:
            return tracked_lot
        self.repository.update_tracked_lot_state(str(tracked_lot["_id"]), payload, updated_at=self._now())
        return {**tracked_lot, **payload}

    @staticmethod
    def _tracked_lot_state_from_snapshot(snapshot: CopartLotSnapshot, detail_etag: str | None = None) -> dict:
        payload = {
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

    @staticmethod
    def serialize_tracked_lot(document: dict) -> dict:
        return {
            "id": str(document["_id"]),
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
    def _now() -> datetime:
        return datetime.now(timezone.utc)
