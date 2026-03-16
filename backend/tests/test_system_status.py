from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Optional

import mongomock
from fastapi.testclient import TestClient
import pytest


ROOT = Path(__file__).resolve().parents[1] / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


import cartrap.app as app_module
from cartrap.app import create_app
from cartrap.config import Settings
from cartrap.modules.copart_provider.errors import CopartGatewayUnavailableError
from cartrap.modules.copart_provider.models import CopartLotSnapshot, CopartSearchPage
from cartrap.modules.monitoring.service import MonitoringService
from cartrap.modules.search.schemas import SearchRequest
from cartrap.modules.search.service import SearchService
from cartrap.modules.system_status.repository import SystemStatusRepository
from cartrap.modules.system_status.service import SystemStatusService
from cartrap.modules.watchlist.service import WatchlistService


class FakeMongoManager:
    def __init__(self, uri: str, database_name: str, ping_on_startup: bool = False) -> None:
        self._database_name = database_name
        self._client = None

    def connect(self) -> None:
        self._client = mongomock.MongoClient(tz_aware=True)

    @property
    def database(self):
        return self._client[self._database_name]

    def close(self) -> None:
        self._client = None


class SuccessfulSearchProvider:
    def search_lots(self, payload: dict) -> CopartSearchPage:
        del payload
        return CopartSearchPage(results=[], num_found=3)

    def close(self) -> None:
        return None


class FailingSearchProvider:
    def search_lots(self, payload: dict) -> CopartSearchPage:
        del payload
        raise CopartGatewayUnavailableError("gateway unavailable")

    def close(self) -> None:
        return None


class SuccessfulConditionalSearchProvider:
    def fetch_search_count_conditional(self, payload: dict, etag=None):
        del payload
        del etag
        return type("SearchCountResult", (), {"num_found": 7, "etag": '"etag-1"', "not_modified": False})()

    def close(self) -> None:
        return None


class ConditionalLotProvider:
    def __init__(self, *, snapshot: Optional[CopartLotSnapshot], not_modified: bool, should_fail: bool = False) -> None:
        self._snapshot = snapshot
        self._not_modified = not_modified
        self._should_fail = should_fail

    def fetch_lot_conditional(self, url: str, etag=None):
        del url
        del etag
        if self._should_fail:
            raise CopartGatewayUnavailableError("gateway unavailable")
        return type("FetchResult", (), {"snapshot": self._snapshot, "etag": '"lot-etag"', "not_modified": self._not_modified})()

    def fetch_lot(self, url: str) -> CopartLotSnapshot:
        del url
        if self._snapshot is None:
            raise CopartGatewayUnavailableError("gateway unavailable")
        return self._snapshot

    def close(self) -> None:
        return None


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(app_module, "MongoManager", FakeMongoManager)
    app = create_app(
        Settings(
            app_name="CarTrap Status Test",
            environment="test",
            MONGO_URI="mongodb://unused",
            MONGO_DB="cartrap_test",
            MONGO_PING_ON_STARTUP=False,
        )
    )
    return TestClient(app)


def test_system_status_endpoint_returns_available_state_by_default(client: TestClient) -> None:
    with client:
        response = client.get("/api/system/status")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "CarTrap Status Test",
        "environment": "test",
        "live_sync": {
            "status": "available",
            "last_success_at": None,
            "last_success_source": None,
            "last_failure_at": None,
            "last_failure_source": None,
            "last_error_message": None,
            "stale": False,
        },
    }


def test_system_status_endpoint_treats_stale_failure_marker_as_available(client: TestClient) -> None:
    stale_now = datetime(2026, 3, 16, 13, 0, tzinfo=timezone.utc)
    stale_failure = datetime(2026, 3, 16, 12, 40, tzinfo=timezone.utc)

    with client:
        repository = SystemStatusRepository(client.app.state.mongo.database)
        repository.set_live_sync_degraded(stale_failure, "watchlist_poll", "gateway unavailable")
        status_service = SystemStatusService(client.app.state.mongo.database, now_provider=lambda: stale_now)
        live_sync = status_service.get_live_sync_status()

    assert live_sync["status"] == "available"
    assert live_sync["stale"] is True
    assert live_sync["last_failure_source"] == "watchlist_poll"


def test_search_service_marks_live_sync_degraded_and_then_available() -> None:
    database = mongomock.MongoClient(tz_aware=True)["cartrap_test"]
    status_service = SystemStatusService(database)
    search_request = SearchRequest(make="Ford")

    service = SearchService(database, provider_factory=lambda: FailingSearchProvider())
    with pytest.raises(Exception):
        service.search(search_request)

    degraded_status = status_service.get_live_sync_status()
    assert degraded_status["status"] == "degraded"
    assert degraded_status["last_failure_source"] == "manual_search"
    assert degraded_status["last_error_message"] == "gateway unavailable"

    healthy_service = SearchService(database, provider_factory=lambda: SuccessfulSearchProvider())
    result = healthy_service.search(search_request)

    assert result["total_results"] == 3
    available_status = status_service.get_live_sync_status()
    assert available_status["status"] == "available"
    assert available_status["last_success_source"] == "manual_search"


def test_saved_search_poll_marks_live_sync_available_on_success() -> None:
    database = mongomock.MongoClient(tz_aware=True)["cartrap_test"]
    service = SearchService(database, provider_factory=lambda: SuccessfulConditionalSearchProvider())

    result = service.fetch_result_count(SearchRequest(make="Ford"))
    status_service = SystemStatusService(database)
    live_sync = status_service.get_live_sync_status()

    assert result == {"result_count": 7, "etag": '"etag-1"', "not_modified": False}
    assert live_sync["status"] == "available"
    assert live_sync["last_success_source"] == "saved_search_poll"


def test_monitoring_service_marks_live_sync_failure_and_recovery() -> None:
    database = mongomock.MongoClient(tz_aware=True)["cartrap_test"]
    initial_snapshot = CopartLotSnapshot(
        lot_number="12345678",
        title="2020 TOYOTA CAMRY SE",
        url="https://www.copart.com/lot/12345678",
        thumbnail_url=None,
        image_urls=[],
        odometer=None,
        primary_damage=None,
        estimated_retail_value=None,
        has_key=None,
        drivetrain=None,
        highlights=[],
        vin=None,
        status="upcoming",
        raw_status="Upcoming",
        sale_date=datetime(2026, 3, 20, 17, 0, tzinfo=timezone.utc),
        current_bid=1000.0,
        buy_now_price=None,
        currency="USD",
    )
    watchlist_service = WatchlistService(database, provider_factory=lambda: ConditionalLotProvider(snapshot=initial_snapshot, not_modified=False))
    watchlist_service.add_tracked_lot({"id": "user-1"}, "https://www.copart.com/lot/12345678")

    failing_monitoring = MonitoringService(
        database,
        provider_factory=lambda: ConditionalLotProvider(snapshot=None, not_modified=False, should_fail=True),
    )
    failing_monitoring.poll_due_lots(now=datetime(2026, 3, 20, 16, 30, tzinfo=timezone.utc))
    status_service = SystemStatusService(database)
    degraded_status = status_service.get_live_sync_status()
    assert degraded_status["status"] == "degraded"
    assert degraded_status["last_failure_source"] == "watchlist_poll"

    recovering_monitoring = MonitoringService(
        database,
        provider_factory=lambda: ConditionalLotProvider(snapshot=None, not_modified=True),
    )
    recovering_monitoring.poll_due_lots(now=datetime(2026, 3, 20, 16, 45, tzinfo=timezone.utc))
    available_status = status_service.get_live_sync_status()
    assert available_status["status"] == "available"
    assert available_status["last_success_source"] == "watchlist_poll"
