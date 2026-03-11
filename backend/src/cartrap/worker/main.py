"""Background worker entrypoint for polling tracked lots."""

from __future__ import annotations

import logging
import time

from cartrap.config import get_settings
from cartrap.db.mongo import MongoManager
from cartrap.modules.monitoring.service import MonitoringService


LOGGER = logging.getLogger(__name__)


def run_polling_loop(sleep_seconds: int = 30) -> None:
    settings = get_settings()
    mongo = MongoManager(settings.mongo_uri, settings.mongo_db, settings.mongo_ping_on_startup)
    mongo.connect()
    monitoring_service = MonitoringService(mongo.database)

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
