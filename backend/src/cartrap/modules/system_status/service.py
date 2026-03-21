"""Shared live-sync status service for API and worker processes."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
from typing import Callable, Optional, Union

from pymongo.database import Database

from cartrap.core.logging import make_log_extra, new_correlation_id
from cartrap.modules.system_status.repository import SystemStatusRepository


LIVE_SYNC_STALE_AFTER = timedelta(minutes=10)
logger = logging.getLogger(__name__)


def build_freshness_envelope(
    *,
    last_synced_at: datetime | None,
    stale_after_window: timedelta,
    live_sync_status: dict | None = None,
    current_time: datetime | None = None,
) -> dict:
    now = current_time or datetime.now(timezone.utc)
    stale_after = last_synced_at + stale_after_window if last_synced_at is not None else None
    is_outdated = stale_after is not None and now > stale_after
    degraded_reason = None
    retryable = False

    if live_sync_status is not None and live_sync_status.get("status") == "degraded":
        degraded_reason = live_sync_status.get("last_error_message")
        retryable = True

    if last_synced_at is None:
        freshness_status = "degraded" if degraded_reason else "unknown"
    elif degraded_reason:
        freshness_status = "degraded" if is_outdated else "cached"
    elif is_outdated:
        freshness_status = "outdated"
    else:
        freshness_status = "live"

    return {
        "status": freshness_status,
        "last_synced_at": last_synced_at,
        "stale_after": stale_after,
        "degraded_reason": degraded_reason,
        "retryable": retryable,
    }


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
        document = self._repository.set_live_sync_available(timestamp, source)
        logger.info(
            "live_sync.available",
            extra=make_log_extra(
                "live_sync.available",
                correlation_id=new_correlation_id("live-sync"),
                source=source,
                checked_at=timestamp,
            ),
        )
        return document

    def mark_live_sync_degraded(
        self,
        source: str,
        reason: Union[Exception, str],
        checked_at: Optional[datetime] = None,
    ) -> dict:
        timestamp = checked_at or self._now_provider()
        message = str(reason).strip() or "Unknown live sync error."
        document = self._repository.set_live_sync_degraded(timestamp, source, message)
        logger.warning(
            "live_sync.degraded",
            extra=make_log_extra(
                "live_sync.degraded",
                correlation_id=new_correlation_id("live-sync"),
                source=source,
                checked_at=timestamp,
                error_message=message,
                error_type=type(reason).__name__ if isinstance(reason, Exception) else "message",
            ),
        )
        return document

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
