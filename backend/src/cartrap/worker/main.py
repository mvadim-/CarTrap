"""Background worker entrypoint for polling tracked lots."""

from __future__ import annotations

import logging
import time
from typing import Optional

from cartrap.config import get_settings
from cartrap.core.logging import configure_logging, make_log_extra, new_correlation_id
from cartrap.db.mongo import MongoManager
from cartrap.modules.monitoring.service import MonitoringService
from cartrap.modules.notifications.service import NotificationService, build_web_push_sender
from cartrap.modules.provider_connections.service import ProviderConnectionService
from cartrap.modules.search.service import SearchService
from cartrap.modules.system_status.service import SystemStatusService


LOGGER = logging.getLogger(__name__)


def run_single_poll_cycle(
    monitoring_service: MonitoringService,
    search_service: SearchService,
    system_status_service: Optional[SystemStatusService] = None,
) -> dict[str, dict]:
    correlation_id = new_correlation_id("worker-cycle")
    watchlist_result = {
        "processed": 0,
        "updated": 0,
        "failed": 0,
        "skipped": 0,
        "events": [],
        "jobs": [],
    }
    saved_search_result = {
        "processed": 0,
        "updated": 0,
        "failed": 0,
        "notified": 0,
        "skipped": 0,
        "events": [],
        "jobs": [],
    }

    try:
        watchlist_result = monitoring_service.poll_due_lots()
    except Exception as exc:
        if system_status_service is not None:
            system_status_service.mark_live_sync_degraded("watchlist_poll", exc)
        LOGGER.exception(
            "worker.poll_cycle.watchlist_failed",
            extra=make_log_extra(
                "worker.poll_cycle.watchlist_failed",
                correlation_id=correlation_id,
                error_type=type(exc).__name__,
                error_message=str(exc),
            ),
        )

    try:
        saved_search_result = search_service.poll_due_saved_searches()
    except Exception as exc:
        if system_status_service is not None:
            system_status_service.mark_live_sync_degraded("saved_search_poll", exc)
        LOGGER.exception(
            "worker.poll_cycle.saved_search_failed",
            extra=make_log_extra(
                "worker.poll_cycle.saved_search_failed",
                correlation_id=correlation_id,
                error_type=type(exc).__name__,
                error_message=str(exc),
            ),
        )

    LOGGER.info(
        "worker.poll_cycle.completed",
        extra=make_log_extra(
            "worker.poll_cycle.completed",
            correlation_id=correlation_id,
            watchlist_processed=watchlist_result["processed"],
            watchlist_updated=watchlist_result["updated"],
            watchlist_failed=watchlist_result["failed"],
            watchlist_skipped=watchlist_result["skipped"],
            saved_search_processed=saved_search_result["processed"],
            saved_search_updated=saved_search_result["updated"],
            saved_search_failed=saved_search_result["failed"],
            saved_search_notified=saved_search_result["notified"],
            saved_search_skipped=saved_search_result["skipped"],
        ),
    )
    return {
        "watchlist": watchlist_result,
        "saved_search": saved_search_result,
    }


def run_polling_loop(sleep_seconds: int = 30) -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    mongo = MongoManager(settings.mongo_uri, settings.mongo_db, settings.mongo_ping_on_startup)
    mongo.connect()
    sender = build_web_push_sender(settings.vapid_private_key, settings.vapid_subject)
    notification_service = NotificationService(
        mongo.database,
        sender=sender,
        vapid_public_key=settings.vapid_public_key,
        vapid_private_key=settings.vapid_private_key,
        vapid_subject=settings.vapid_subject,
    )
    system_status_service = SystemStatusService(mongo.database)
    provider_connection_service = ProviderConnectionService(mongo.database, settings=settings)
    monitoring_service = MonitoringService(
        mongo.database,
        notification_service=notification_service,
        default_poll_interval_minutes=settings.watchlist_default_poll_interval_minutes,
        near_auction_poll_interval_minutes=settings.watchlist_near_auction_poll_interval_minutes,
        near_auction_window_minutes=settings.watchlist_near_auction_window_minutes,
        provider_connection_service=provider_connection_service,
    )
    search_service = SearchService(
        mongo.database,
        notification_service=notification_service,
        saved_search_poll_interval_minutes=settings.saved_search_poll_interval_minutes,
        provider_connection_service=provider_connection_service,
    )

    try:
        while True:
            run_single_poll_cycle(monitoring_service, search_service, system_status_service=system_status_service)
            time.sleep(sleep_seconds)
    finally:
        mongo.close()


if __name__ == "__main__":
    run_polling_loop()
