"""Shared live-sync status service for API and worker processes."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Callable, Optional, Union

from pymongo.database import Database

from cartrap.modules.system_status.repository import SystemStatusRepository


LIVE_SYNC_STALE_AFTER = timedelta(minutes=10)


class SystemStatusService:
    def __init__(
        self,
        database: Database,
        now_provider: Optional[Callable[[], datetime]] = None,
    ) -> None:
        self._repository = SystemStatusRepository(database)
        self._now_provider = now_provider or self._now

    def mark_live_sync_available(self, source: str, checked_at: Optional[datetime] = None) -> dict:
        timestamp = checked_at or self._now_provider()
        return self._repository.set_live_sync_available(timestamp, source)

    def mark_live_sync_degraded(
        self,
        source: str,
        reason: Union[Exception, str],
        checked_at: Optional[datetime] = None,
    ) -> dict:
        timestamp = checked_at or self._now_provider()
        message = str(reason).strip() or "Unknown live sync error."
        return self._repository.set_live_sync_degraded(timestamp, source, message)

    def get_live_sync_status(self) -> dict:
        document = self._repository.get_live_sync_status()
        current_time = self._now_provider()
        if document is None:
            return {
                "status": "available",
                "last_success_at": None,
                "last_success_source": None,
                "last_failure_at": None,
                "last_failure_source": None,
                "last_error_message": None,
                "stale": False,
            }

        last_success_at = document.get("last_success_at")
        last_failure_at = document.get("last_failure_at")
        stale = bool(
            document.get("availability") == "degraded"
            and last_failure_at is not None
            and current_time - last_failure_at > LIVE_SYNC_STALE_AFTER
            and (last_success_at is None or last_failure_at >= last_success_at)
        )
        effective_status = "available" if stale else document.get("availability", "available")
        return {
            "status": effective_status,
            "last_success_at": last_success_at,
            "last_success_source": document.get("last_success_source"),
            "last_failure_at": last_failure_at,
            "last_failure_source": document.get("last_failure_source"),
            "last_error_message": document.get("last_error_message"),
            "stale": stale,
        }

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)
