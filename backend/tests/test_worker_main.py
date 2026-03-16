from pathlib import Path
import sys
from typing import Optional


ROOT = Path(__file__).resolve().parents[1] / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from cartrap.worker.main import run_single_poll_cycle


class FakeMonitoringService:
    def __init__(self, result: Optional[dict] = None, should_fail: bool = False) -> None:
        self._result = result or {"processed": 1, "updated": 0, "failed": 0, "events": []}
        self._should_fail = should_fail
        self.calls = 0

    def poll_due_lots(self) -> dict:
        self.calls += 1
        if self._should_fail:
            raise RuntimeError("gateway unavailable")
        return self._result


class FakeSearchService:
    def __init__(self, result: Optional[dict] = None, should_fail: bool = False) -> None:
        self._result = result or {"processed": 2, "updated": 1, "failed": 0, "notified": 1, "events": []}
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
        "watchlist": {"processed": 1, "updated": 0, "failed": 0, "events": []},
        "saved_search": {"processed": 2, "updated": 1, "failed": 0, "notified": 1, "events": []},
    }


def test_run_single_poll_cycle_treats_watchlist_failure_as_transient() -> None:
    monitoring = FakeMonitoringService(should_fail=True)
    search = FakeSearchService()
    system_status = FakeSystemStatusService()

    result = run_single_poll_cycle(monitoring, search, system_status_service=system_status)

    assert monitoring.calls == 1
    assert search.calls == 1
    assert result["watchlist"] == {"processed": 0, "updated": 0, "failed": 0, "events": []}
    assert result["saved_search"] == {"processed": 2, "updated": 1, "failed": 0, "notified": 1, "events": []}
    assert system_status.events == [("watchlist_poll", "gateway unavailable")]


def test_run_single_poll_cycle_treats_saved_search_failure_as_transient() -> None:
    monitoring = FakeMonitoringService()
    search = FakeSearchService(should_fail=True)
    system_status = FakeSystemStatusService()

    result = run_single_poll_cycle(monitoring, search, system_status_service=system_status)

    assert monitoring.calls == 1
    assert search.calls == 1
    assert result["watchlist"] == {"processed": 1, "updated": 0, "failed": 0, "events": []}
    assert result["saved_search"] == {
        "processed": 0,
        "updated": 0,
        "failed": 0,
        "notified": 0,
        "events": [],
    }
    assert system_status.events == [("saved_search_poll", "gateway unavailable")]
