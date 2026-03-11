from __future__ import annotations

from pathlib import Path
import sys

from datetime import datetime, timezone

import mongomock
from fastapi.testclient import TestClient
import pytest


ROOT = Path(__file__).resolve().parents[2] / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


import cartrap.app as app_module
from cartrap.config import Settings
from cartrap.modules.copart_provider.models import CopartLotSnapshot, CopartSearchResult
from cartrap.modules.search.schemas import SearchRequest


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


class FakeProvider:
    def __init__(self, results: list[CopartSearchResult], lots: dict[str, CopartLotSnapshot], should_fail: bool = False) -> None:
        self._results = results
        self._lots = lots
        self._should_fail = should_fail

    def search_lots(self, url: str) -> list[CopartSearchResult]:
        if self._should_fail:
            raise RuntimeError("upstream failed")
        return self._results

    def fetch_lot(self, url: str) -> CopartLotSnapshot:
        if self._should_fail:
            raise RuntimeError("upstream failed")
        return self._lots[url]

    def close(self) -> None:
        return None


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(app_module, "MongoManager", FakeMongoManager)
    settings = Settings(
        environment="test",
        mongo_uri="mongodb://unused",
        mongo_db="cartrap_test",
        jwt_secret="test-secret-123-test-secret-123x",
        jwt_refresh_secret="refresh-secret-123-refresh-secret-123",
        bootstrap_admin_email="admin@example.com",
        bootstrap_admin_password="AdminPass123",
    )
    app = app_module.create_app(settings)
    app.state.copart_provider_factory = lambda: FakeProvider(
        results=[
            CopartSearchResult(
                lot_number="12345678",
                title="2020 TOYOTA CAMRY SE",
                url="https://www.copart.com/lot/12345678",
                location="CA - SACRAMENTO",
                sale_date=datetime(2026, 3, 20, 17, 0, tzinfo=timezone.utc),
                current_bid=4200.0,
                currency="USD",
                status="live",
            ),
            CopartSearchResult(
                lot_number="87654321",
                title="2018 HONDA CIVIC EX",
                url="https://www.copart.com/lot/87654321",
                location="TX - DALLAS",
                sale_date=datetime(2026, 3, 21, 18, 30, tzinfo=timezone.utc),
                current_bid=1800.0,
                currency="USD",
                status="upcoming",
            ),
        ],
        lots={
            "https://www.copart.com/lot/12345678": CopartLotSnapshot(
                lot_number="12345678",
                title="2020 TOYOTA CAMRY SE",
                url="https://www.copart.com/lot/12345678",
                status="on_approval",
                raw_status="On Approval",
                sale_date=datetime(2026, 3, 20, 17, 0, tzinfo=timezone.utc),
                current_bid=4200.0,
                buy_now_price=6500.0,
                currency="USD",
            )
        },
    )
    return TestClient(app)


def _login(client: TestClient, email: str, password: str) -> str:
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    return response.json()["access_token"]


def _create_user(client: TestClient, email: str, password: str) -> str:
    admin_token = _login(client, "admin@example.com", "AdminPass123")
    invite = client.post(
        "/api/admin/invites",
        json={"email": email},
        headers={"Authorization": f"Bearer {admin_token}"},
    ).json()
    client.post("/api/auth/invites/accept", json={"token": invite["token"], "password": password})
    return _login(client, email, password)


def test_search_endpoint_returns_results(client: TestClient) -> None:
    with client:
        user_token = _create_user(client, "searcher@example.com", "SearcherPass123")
        response = client.post(
            "/api/search",
            json={"query": "toyota camry", "location": "CA"},
            headers={"Authorization": f"Bearer {user_token}"},
        )

    assert response.status_code == 200
    assert len(response.json()["results"]) == 2
    assert response.json()["source_url"].startswith("https://www.copart.com/lotSearchResults?")
    assert "searchCriteria=" in response.json()["source_url"]


def test_add_from_search_reuses_watchlist_logic(client: TestClient) -> None:
    with client:
        user_token = _create_user(client, "search-add@example.com", "SearchAddPass123")
        response = client.post(
            "/api/search/watchlist",
            json={"lot_url": "https://www.copart.com/lot/12345678"},
            headers={"Authorization": f"Bearer {user_token}"},
        )

    assert response.status_code == 201
    assert response.json()["tracked_lot"]["lot_number"] == "12345678"


def test_search_rejects_invalid_filters(client: TestClient) -> None:
    with client:
        user_token = _create_user(client, "invalid@example.com", "InvalidPass123")
        response = client.post(
            "/api/search",
            json={},
            headers={"Authorization": f"Bearer {user_token}"},
        )

    assert response.status_code == 422


def test_search_returns_empty_results(client: TestClient) -> None:
    with client:
        user_token = _create_user(client, "empty@example.com", "EmptyPass123")
        client.app.state.copart_provider_factory = lambda: FakeProvider(results=[], lots={})
        response = client.post(
            "/api/search",
            json={"search_url": "https://www.copart.com/search?query=honda"},
            headers={"Authorization": f"Bearer {user_token}"},
        )

    assert response.status_code == 200
    assert response.json()["results"] == []


def test_search_handles_provider_failure(client: TestClient) -> None:
    with client:
        user_token = _create_user(client, "broken@example.com", "BrokenPass123")
        client.app.state.copart_provider_factory = lambda: FakeProvider(results=[], lots={}, should_fail=True)
        response = client.post(
            "/api/search",
            json={"query": "broken"},
            headers={"Authorization": f"Bearer {user_token}"},
        )

    assert response.status_code == 502
    assert response.json()["detail"] == "Failed to fetch search results from Copart."


def test_search_request_builds_lot_search_results_url() -> None:
    request = SearchRequest(query="Ford mustang mach-e", location="NJ")

    source_url = request.to_url()

    assert source_url.startswith("https://www.copart.com/lotSearchResults?")
    assert "free=true" in source_url
    assert "from=%2FvehicleFinder" in source_url
    assert "Ford+mustang+mach-e" in source_url
