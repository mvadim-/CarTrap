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
        snapshot = self._fetch_snapshot(lot_url)
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
                "status": snapshot.status,
                "raw_status": snapshot.raw_status,
                "sale_date": snapshot.sale_date,
                "current_bid": snapshot.current_bid,
                "buy_now_price": snapshot.buy_now_price,
                "currency": snapshot.currency,
                "last_checked_at": now,
                "active": True,
                "created_at": now,
                "updated_at": now,
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
        items = [self.serialize_tracked_lot(item) for item in self.repository.list_tracked_lots_for_owner(owner_user["id"])]
        return {"items": items}

    def remove_tracked_lot(self, owner_user: dict, tracked_lot_id: str) -> None:
        tracked_lot = self.repository.find_tracked_lot_by_id_for_owner(tracked_lot_id, owner_user["id"])
        if tracked_lot is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tracked lot not found.")
        self.repository.delete_tracked_lot(tracked_lot_id)

    def _fetch_snapshot(self, lot_url: str) -> CopartLotSnapshot:
        provider = self._provider_factory()
        try:
            return provider.fetch_lot(lot_url)
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

    @staticmethod
    def serialize_tracked_lot(document: dict) -> dict:
        return {
            "id": str(document["_id"]),
            "lot_number": document["lot_number"],
            "url": document["url"],
            "title": document["title"],
            "status": document["status"],
            "raw_status": document["raw_status"],
            "current_bid": document.get("current_bid"),
            "buy_now_price": document.get("buy_now_price"),
            "currency": document["currency"],
            "sale_date": document.get("sale_date"),
            "last_checked_at": document["last_checked_at"],
            "created_at": document["created_at"],
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
