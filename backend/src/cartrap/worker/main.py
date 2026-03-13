"""Background worker entrypoint for polling tracked lots."""

from __future__ import annotations

import logging
import time

from cartrap.config import get_settings
from cartrap.db.mongo import MongoManager
from cartrap.modules.monitoring.service import MonitoringService
from cartrap.modules.notifications.service import NotificationService, build_web_push_sender


LOGGER = logging.getLogger(__name__)


def run_polling_loop(sleep_seconds: int = 30) -> None:
    settings = get_settings()
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
    monitoring_service = MonitoringService(mongo.database, notification_service=notification_service)

    try:
        while True:
            result = monitoring_service.poll_due_lots()
            LOGGER.info(
                "Worker poll cycle complete",
                extra={
                    "processed": result["processed"],
                    "updated": result["updated"],
                    "failed": result["failed"],
                },
            )
            time.sleep(sleep_seconds)
    finally:
        mongo.close()


if __name__ == "__main__":
    run_polling_loop()
