from pathlib import Path
import logging
import sys
from typing import Optional

from datetime import datetime, timedelta, timezone

import mongomock

ROOT = Path(__file__).resolve().parents[1] / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from cartrap.config import Settings
from cartrap.modules.notifications.service import NotificationService
from cartrap.modules.monitoring.job_runtime import JobRuntimeService
from cartrap.modules.provider_connections.service import ProviderConnectionService
from cartrap.modules.runtime_settings.service import RuntimeSettingsService
from cartrap.worker.main import build_cycle_services, run_single_poll_cycle


class FakeMonitoringService:
    def __init__(self, result: Optional[dict] = None, should_fail: bool = False) -> None:
        self._result = result or {"processed": 1, "updated": 0, "failed": 0, "skipped": 0, "events": [], "jobs": []}
        self._should_fail = should_fail
        self.calls = 0

    def poll_due_lots(self) -> dict:
        self.calls += 1
        if self._should_fail:
            raise RuntimeError("gateway unavailable")
        return self._result


class FakeSearchService:
    def __init__(self, result: Optional[dict] = None, should_fail: bool = False) -> None:
        self._result = result or {
            "processed": 2,
            "updated": 1,
            "failed": 0,
            "notified": 1,
            "skipped": 0,
            "events": [],
            "jobs": [],
        }
        self._should_fail = should_fail
        self.calls = 0

    def poll_due_saved_searches(self) -> dict:
        self.calls += 1
        if self._should_fail:
            raise RuntimeError("gateway unavailable")
        return self._result


class FakeSystemStatusService:
    def __init__(self) -> None:
        self.events: list[tuple[str, str]] = []

    def mark_live_sync_degraded(self, source: str, reason) -> None:
        self.events.append((source, str(reason)))


def test_run_single_poll_cycle_returns_both_results_when_services_succeed() -> None:
    monitoring = FakeMonitoringService()
    search = FakeSearchService()

    result = run_single_poll_cycle(monitoring, search)

    assert monitoring.calls == 1
    assert search.calls == 1
    assert result == {
        "watchlist": {"processed": 1, "updated": 0, "failed": 0, "skipped": 0, "events": [], "jobs": []},
        "saved_search": {
            "processed": 2,
            "updated": 1,
            "failed": 0,
            "notified": 1,
            "skipped": 0,
            "events": [],
            "jobs": [],
        },
    }


def test_run_single_poll_cycle_logs_structured_summary(caplog) -> None:
    monitoring = FakeMonitoringService()
    search = FakeSearchService()

    with caplog.at_level(logging.INFO):
        run_single_poll_cycle(monitoring, search)

    summary_record = next(record for record in caplog.records if getattr(record, "event", "") == "worker.poll_cycle.completed")
    assert summary_record.structured["correlation_id"].startswith("worker-cycle-")
    assert summary_record.structured["watchlist_processed"] == 1
    assert summary_record.structured["saved_search_notified"] == 1


def test_run_single_poll_cycle_treats_watchlist_failure_as_transient() -> None:
    monitoring = FakeMonitoringService(should_fail=True)
    search = FakeSearchService()
    system_status = FakeSystemStatusService()

    result = run_single_poll_cycle(monitoring, search, system_status_service=system_status)

    assert monitoring.calls == 1
    assert search.calls == 1
    assert result["watchlist"] == {"processed": 0, "updated": 0, "failed": 0, "skipped": 0, "events": [], "jobs": []}
    assert result["saved_search"] == {
        "processed": 2,
        "updated": 1,
        "failed": 0,
        "notified": 1,
        "skipped": 0,
        "events": [],
        "jobs": [],
    }
    assert system_status.events == [("watchlist_poll", "gateway unavailable")]


def test_run_single_poll_cycle_treats_saved_search_failure_as_transient() -> None:
    monitoring = FakeMonitoringService()
    search = FakeSearchService(should_fail=True)
    system_status = FakeSystemStatusService()

    result = run_single_poll_cycle(monitoring, search, system_status_service=system_status)

    assert monitoring.calls == 1
    assert search.calls == 1
    assert result["watchlist"] == {"processed": 1, "updated": 0, "failed": 0, "skipped": 0, "events": [], "jobs": []}
    assert result["saved_search"] == {
        "processed": 0,
        "updated": 0,
        "failed": 0,
        "notified": 0,
        "skipped": 0,
        "events": [],
        "jobs": [],
    }
    assert system_status.events == [("saved_search_poll", "gateway unavailable")]


def test_job_runtime_acquire_complete_and_backoff_lifecycle() -> None:
    database = mongomock.MongoClient(tz_aware=True)["cartrap_test"]
    runtime_service = JobRuntimeService(database, lease_seconds=60, retry_backoff_seconds=30)
    now = datetime(2026, 3, 21, 16, 0, tzinfo=timezone.utc)

    first = runtime_service.acquire(job_type="saved_search_poll", resource_id="saved-1", now=now)
    assert first is not None
    assert runtime_service.acquire(job_type="saved_search_poll", resource_id="saved-1", now=now + timedelta(seconds=10)) is None

    failed = runtime_service.fail_retryable(
        first,
        now=now + timedelta(seconds=15),
        outcome="refresh_failed",
        error_message="gateway unavailable",
    )
    assert failed["status"] == "retryable_failure"
    assert failed["next_retry_at"] == now + timedelta(seconds=45)

    assert runtime_service.acquire(job_type="saved_search_poll", resource_id="saved-1", now=now + timedelta(seconds=20)) is None
    retry = runtime_service.acquire(job_type="saved_search_poll", resource_id="saved-1", now=now + timedelta(seconds=46))
    assert retry is not None
    assert retry["attempt_count"] == 2

    completed = runtime_service.complete(retry, now=now + timedelta(seconds=50), outcome="refreshed")
    assert completed["status"] == "succeeded"
    assert completed["attempt_count"] == 2


def test_build_cycle_services_reads_runtime_settings_each_cycle() -> None:
    database = mongomock.MongoClient(tz_aware=True)["cartrap_test"]
    settings = Settings()
    runtime_settings_service = RuntimeSettingsService(database, settings)
    notification_service = NotificationService(database)
    provider_connection_service = ProviderConnectionService(database, settings=settings)

    first_monitoring, first_search, first_status = build_cycle_services(
        database=database,
        settings=settings,
        notification_service=notification_service,
        provider_connection_service=provider_connection_service,
        runtime_settings_service=runtime_settings_service,
    )
    runtime_settings_service.update_settings(
        {
            "saved_search_poll_interval_minutes": 9,
            "watchlist_default_poll_interval_minutes": 11,
            "watchlist_auction_reminder_offsets_minutes": [30, 5, 0],
            "job_retry_backoff_seconds": 75,
            "live_sync_stale_after_minutes": 20,
        },
        updated_by="admin-user-1",
    )
    second_monitoring, second_search, second_status = build_cycle_services(
        database=database,
        settings=settings,
        notification_service=notification_service,
        provider_connection_service=provider_connection_service,
        runtime_settings_service=runtime_settings_service,
    )

    assert first_search._saved_search_poll_interval_minutes == settings.saved_search_poll_interval_minutes
    assert second_search._saved_search_poll_interval_minutes == 9
    assert first_monitoring._default_poll_interval_minutes == settings.watchlist_default_poll_interval_minutes
    assert second_monitoring._default_poll_interval_minutes == 11
    assert second_monitoring._auction_reminder_offsets_minutes == (30, 5, 0)
    assert second_search._refresh_job_runtime._retry_backoff_seconds == 75
    assert second_monitoring._refresh_job_runtime._retry_backoff_seconds == 75
    assert first_status._live_sync_stale_after == timedelta(minutes=settings.live_sync_stale_after_minutes)
    assert second_status._live_sync_stale_after == timedelta(minutes=20)
