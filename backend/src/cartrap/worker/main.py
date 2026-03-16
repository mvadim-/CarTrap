"""Background worker entrypoint for polling tracked lots."""

from __future__ import annotations

import logging
import time
from typing import Optional

from cartrap.config import get_settings
from cartrap.core.logging import configure_logging
from cartrap.db.mongo import MongoManager
from cartrap.modules.monitoring.service import MonitoringService
from cartrap.modules.notifications.service import NotificationService, build_web_push_sender
from cartrap.modules.search.service import SearchService
from cartrap.modules.system_status.service import SystemStatusService


LOGGER = logging.getLogger(__name__)


def run_single_poll_cycle(
    monitoring_service: MonitoringService,
    search_service: SearchService,
    system_status_service: Optional[SystemStatusService] = None,
) -> dict[str, dict]:
    watchlist_result = {
        "processed": 0,
        "updated": 0,
        "failed": 0,
        "events": [],
    }
    saved_search_result = {
        "processed": 0,
        "updated": 0,
        "failed": 0,
        "notified": 0,
        "events": [],
    }

    try:
        watchlist_result = monitoring_service.poll_due_lots()
    except Exception as exc:
        if system_status_service is not None:
            system_status_service.mark_live_sync_degraded("watchlist_poll", exc)
        LOGGER.exception("Worker watchlist polling cycle failed.")

    try:
        saved_search_result = search_service.poll_due_saved_searches()
    except Exception as exc:
        if system_status_service is not None:
            system_status_service.mark_live_sync_degraded("saved_search_poll", exc)
        LOGGER.exception("Worker saved-search polling cycle failed.")

    LOGGER.info(
        "Worker poll cycle complete",
        extra={
            "watchlist_processed": watchlist_result["processed"],
            "watchlist_updated": watchlist_result["updated"],
            "watchlist_failed": watchlist_result["failed"],
            "saved_search_processed": saved_search_result["processed"],
            "saved_search_updated": saved_search_result["updated"],
            "saved_search_failed": saved_search_result["failed"],
            "saved_search_notified": saved_search_result["notified"],
        },
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
    monitoring_service = MonitoringService(mongo.database, notification_service=notification_service)
    search_service = SearchService(mongo.database, notification_service=notification_service)

    try:
        while True:
            run_single_poll_cycle(monitoring_service, search_service, system_status_service=system_status_service)
            time.sleep(sleep_seconds)
    finally:
        mongo.close()


if __name__ == "__main__":
    run_polling_loop()
