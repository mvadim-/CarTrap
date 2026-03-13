from __future__ import annotations

import json
from pathlib import Path
import sys

from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse

import mongomock
from fastapi.testclient import TestClient
import pytest


ROOT = Path(__file__).resolve().parents[2] / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


import cartrap.app as app_module
from cartrap.config import Settings
from cartrap.modules.copart_provider.models import CopartLotSnapshot, CopartSearchPage, CopartSearchResult
from cartrap.modules.search.schemas import SearchRequest
from cartrap.modules.search.service import SearchService


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
    def __init__(
        self,
        results: list[CopartSearchResult],
        lots: dict[str, CopartLotSnapshot],
        should_fail: bool = False,
        num_found: Optional[int] = None,
        page_results: Optional[dict[int, list[CopartSearchResult]]] = None,
    ) -> None:
        self._results = results
        self._lots = lots
        self._should_fail = should_fail
        self._num_found = len(results) if num_found is None else num_found
        self._page_results = page_results or {1: results}
        self.search_payloads: list[dict[str, Any]] = []

    def search_lots(self, payload: dict) -> CopartSearchPage:
        if self._should_fail:
            raise RuntimeError("upstream failed")
        self.search_payloads.append(payload)
        page_number = int(payload.get("pageNumber", 1))
        return CopartSearchPage(results=self._page_results.get(page_number, []), num_found=self._num_found)

    def fetch_lot(self, url: str) -> CopartLotSnapshot:
        if self._should_fail:
            raise RuntimeError("upstream failed")
        return self._lots[url]

    def fetch_search_keywords(self) -> dict:
        return {
            "ford": {
                "text": "manufacturer_make_desc",
                "filterQuery": 'lot_make_desc:"FORD" OR manufacturer_make_desc:"FORD"',
                "type": "MAKE_MODEL",
            }
        }

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
    fake_provider = FakeProvider(
        results=[
            CopartSearchResult(
                lot_number="12345678",
                title="2020 TOYOTA CAMRY SE",
                url="https://www.copart.com/lot/12345678",
                thumbnail_url="https://img.copart.com/12345678.jpg",
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
                thumbnail_url=None,
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
                thumbnail_url="https://img.copart.com/12345678-detail.jpg",
                status="on_approval",
                raw_status="On Approval",
                sale_date=datetime(2026, 3, 20, 17, 0, tzinfo=timezone.utc),
                current_bid=4200.0,
                buy_now_price=6500.0,
                currency="USD",
            )
        },
    )
    app.state.copart_provider_factory = lambda: fake_provider
    app.state.fake_provider = fake_provider
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
            json={"make": "Ford", "model": "Mustang Mach-E", "year_from": 2025, "year_to": 2027},
            headers={"Authorization": f"Bearer {user_token}"},
        )

    assert response.status_code == 200
    assert len(response.json()["results"]) == 2
    assert response.json()["total_results"] == 2
    assert response.json()["results"][0]["thumbnail_url"] == "https://img.copart.com/12345678.jpg"
    assert response.json()["source_request"]["MISC"] == [
        "vehicle_type_code:VEHTYPE_V",
        "lot_year:[2025 TO 2027]",
        "lot_make_code:FORD",
        'lot_model_group:"MUSTANG MACH-E" OR lot_model_desc:"MUSTANG MACH-E"',
    ]


def test_search_fetches_all_pages_from_num_found(client: TestClient) -> None:
    second_page_result = CopartSearchResult(
        lot_number="11112222",
        title="2024 FORD ESCAPE",
        url="https://www.copart.com/lot/11112222",
        thumbnail_url=None,
        location="FL - MIAMI CENTRAL",
        sale_date=datetime(2026, 3, 22, 17, 0, tzinfo=timezone.utc),
        current_bid=3100.0,
        currency="USD",
        status="upcoming",
    )

    with client:
        user_token = _create_user(client, "paging@example.com", "PagingPass123")
        client.app.state.copart_provider_factory = lambda: FakeProvider(
            results=[],
            lots={},
            num_found=21,
            page_results={
                1: client.app.state.fake_provider._results,
                2: [second_page_result],
            },
        )
        response = client.post(
            "/api/search",
            json={"make": "Ford", "model": "Mustang Mach-E", "year_from": 2025, "year_to": 2027},
            headers={"Authorization": f"Bearer {user_token}"},
        )

    assert response.status_code == 200
    assert response.json()["total_results"] == 21
    assert len(response.json()["results"]) == 3


def test_search_catalog_endpoint_returns_seeded_catalog(client: TestClient) -> None:
    with client:
        user_token = _create_user(client, "catalog@example.com", "CatalogPass123")
        response = client.get(
            "/api/search/catalog",
            headers={"Authorization": f"Bearer {user_token}"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["make_count"] >= 300
    assert any(make["slug"] == "ford" for make in payload["makes"])


def test_admin_can_refresh_search_catalog(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_refresh_catalog(self: SearchService) -> dict:
        return {
            "generated_at": "2026-03-12T16:40:00Z",
            "updated_at": "2026-03-12T16:41:00Z",
            "summary": {
                "make_count": 2,
                "model_count": 3,
                "assigned_model_count": 3,
                "exact_match_count": 2,
                "fuzzy_match_count": 1,
                "unassigned_model_count": 0,
                "year_count": 108,
            },
            "years": [2025, 2026],
            "manual_override_count": 1,
            "makes": [
                {
                    "slug": "ford",
                    "name": "FORD",
                    "aliases": [],
                    "search_filter": 'lot_make_desc:"FORD"',
                    "models": [
                        {
                            "slug": "mustangmache",
                            "name": "MUSTANG MACH-E",
                            "search_filter": 'lot_model_desc:"MUSTANG MACH-E"',
                        }
                    ],
                }
            ],
        }

    monkeypatch.setattr(SearchService, "refresh_catalog", fake_refresh_catalog)

    with client:
        admin_token = _login(client, "admin@example.com", "AdminPass123")
        response = client.post(
            "/api/admin/search-catalog/refresh",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    assert response.status_code == 200
    assert response.json()["summary"]["make_count"] == 2


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
    assert response.json()["tracked_lot"]["thumbnail_url"] == "https://img.copart.com/12345678-detail.jpg"


def test_user_can_save_and_list_saved_searches(client: TestClient) -> None:
    with client:
        user_token = _create_user(client, "saved@example.com", "SavedPass123")
        create_response = client.post(
            "/api/search/saved",
            json={
                "make": "Ford",
                "model": "Mustang Mach-E",
                "drive_type": "all_wheel_drive",
                "primary_damage": "hail",
                "title_type": "salvage_title",
                "fuel_type": "electric",
                "lot_condition": "enhanced_vehicles",
                "odometer_range": "under_25000",
                "year_from": 2025,
                "year_to": 2027,
                "result_count": 21,
            },
            headers={"Authorization": f"Bearer {user_token}"},
        )
        list_response = client.get(
            "/api/search/saved",
            headers={"Authorization": f"Bearer {user_token}"},
        )

    assert create_response.status_code == 201
    assert create_response.json()["saved_search"]["label"] == "FORD MUSTANG MACH-E 2025-2027"
    assert create_response.json()["saved_search"]["criteria"]["make"] == "FORD"
    assert create_response.json()["saved_search"]["criteria"]["drive_type"] == "all_wheel_drive"
    assert create_response.json()["saved_search"]["criteria"]["primary_damage"] == "hail"
    assert create_response.json()["saved_search"]["criteria"]["title_type"] == "salvage_title"
    assert create_response.json()["saved_search"]["criteria"]["fuel_type"] == "electric"
    assert create_response.json()["saved_search"]["criteria"]["lot_condition"] == "enhanced_vehicles"
    assert create_response.json()["saved_search"]["criteria"]["odometer_range"] == "under_25000"
    assert create_response.json()["saved_search"]["external_url"].startswith("https://www.copart.com/lotSearchResults?")
    assert create_response.json()["saved_search"]["result_count"] == 21
    assert list_response.status_code == 200
    assert len(list_response.json()["items"]) == 1
    assert list_response.json()["items"][0]["criteria"]["model"] == "MUSTANG MACH-E"
    assert list_response.json()["items"][0]["criteria"]["drive_type"] == "all_wheel_drive"
    assert list_response.json()["items"][0]["criteria"]["title_type"] == "salvage_title"
    assert list_response.json()["items"][0]["criteria"]["fuel_type"] == "electric"
    assert list_response.json()["items"][0]["criteria"]["lot_condition"] == "enhanced_vehicles"
    assert list_response.json()["items"][0]["criteria"]["odometer_range"] == "under_25000"
    assert list_response.json()["items"][0]["external_url"].startswith("https://www.copart.com/lotSearchResults?")
    assert list_response.json()["items"][0]["result_count"] == 21


def test_user_can_delete_saved_search(client: TestClient) -> None:
    with client:
        user_token = _create_user(client, "delete-saved@example.com", "DeleteSavedPass123")
        create_response = client.post(
            "/api/search/saved",
            json={"make": "Ford", "model": "Mustang Mach-E", "result_count": 8},
            headers={"Authorization": f"Bearer {user_token}"},
        )
        saved_search_id = create_response.json()["saved_search"]["id"]
        delete_response = client.delete(
            f"/api/search/saved/{saved_search_id}",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        list_response = client.get(
            "/api/search/saved",
            headers={"Authorization": f"Bearer {user_token}"},
        )

    assert delete_response.status_code == 204
    assert list_response.status_code == 200
    assert list_response.json()["items"] == []


def test_saved_search_duplicate_is_scoped_per_user(client: TestClient) -> None:
    with client:
        owner_token = _create_user(client, "owner-search@example.com", "OwnerSearchPass123")
        other_token = _create_user(client, "other-search@example.com", "OtherSearchPass123")
        payload = {"make": "Ford", "model": "Mustang Mach-E", "year_from": 2025, "year_to": 2027}
        headers = {"Authorization": f"Bearer {owner_token}"}

        first_response = client.post("/api/search/saved", json=payload, headers=headers)
        duplicate_response = client.post("/api/search/saved", json=payload, headers=headers)
        other_user_response = client.post(
            "/api/search/saved",
            json=payload,
            headers={"Authorization": f"Bearer {other_token}"},
        )

    assert first_response.status_code == 201
    assert duplicate_response.status_code == 409
    assert duplicate_response.json()["detail"] == "Search is already saved."
    assert other_user_response.status_code == 201


def test_saved_search_list_is_user_scoped(client: TestClient) -> None:
    with client:
        owner_token = _create_user(client, "scope-owner@example.com", "ScopeOwnerPass123")
        other_token = _create_user(client, "scope-other@example.com", "ScopeOtherPass123")
        client.post(
            "/api/search/saved",
            json={"make": "Ford", "model": "Mustang Mach-E"},
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        client.post(
            "/api/search/saved",
            json={"make": "Honda", "model": "Civic"},
            headers={"Authorization": f"Bearer {other_token}"},
        )
        owner_list = client.get("/api/search/saved", headers={"Authorization": f"Bearer {owner_token}"})

    assert owner_list.status_code == 200
    assert len(owner_list.json()["items"]) == 1
    assert owner_list.json()["items"][0]["criteria"]["make"] == "FORD"


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
            json={"make": "Honda", "model": "Civic"},
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
            json={"make": "Ford", "model": "Broken"},
            headers={"Authorization": f"Bearer {user_token}"},
        )

    assert response.status_code == 502
    assert response.json()["detail"] == "Failed to fetch search results from Copart."


def test_search_request_builds_api_payload() -> None:
    request = SearchRequest(make="Ford", model="Mustang Mach-E", year_from=2025, year_to=2027)

    payload = request.to_api_request(datetime(2026, 3, 12, 15, 45, tzinfo=timezone.utc)).to_payload()

    assert payload["MISC"] == [
        "vehicle_type_code:VEHTYPE_V",
        "lot_year:[2025 TO 2027]",
        "lot_make_code:FORD",
        'lot_model_group:"MUSTANG MACH-E" OR lot_model_desc:"MUSTANG MACH-E"',
    ]
    assert payload["filter"] == []
    assert payload["pageNumber"] == 1
    assert payload["userStartUtcDatetime"] == "2026-03-12T00:00:00Z"


def test_search_request_builds_structured_filters_payload() -> None:
    request = SearchRequest(
        make="Ford",
        model="Mustang Mach-E",
        drive_type="all_wheel_drive",
        primary_damage="hail",
        title_type="salvage_title",
        fuel_type="electric",
        lot_condition="enhanced_vehicles",
        odometer_range="under_25000",
    )

    payload = request.to_api_request(datetime(2026, 3, 12, 15, 45, tzinfo=timezone.utc)).to_payload()

    assert payload["filter"] == [
        '(drive:"ALL WHEEL DRIVE" OR drive:"All Wheel Drive")',
        "(damage_type_code:DAMAGECODE_HL)",
        "(title_group_code:TITLEGROUP_S)",
        '(fuel_type_desc:"ELECTRIC" OR fuel_type_desc:"Electric")',
        "(lot_condition_code:CERT-E)",
        "(odometer_reading_received:[* TO 25000])",
    ]


def test_search_request_prefers_catalog_filters() -> None:
    request = SearchRequest(
        make="TOYOTA",
        model="CAMRY",
        make_filter='(lot_make_desc:"TOYO" OR manufacturer_make_desc:"TOYO") OR (lot_make_desc:"TOYOTA" OR manufacturer_make_desc:"TOYOTA")',
        model_filter='lot_model_desc:"CAMRY" OR lot_model_group:"CAMRY" OR manufacturer_model_desc:"CAMRY"',
    )

    payload = request.to_api_request(datetime(2026, 3, 12, 15, 45, tzinfo=timezone.utc)).to_payload()

    assert payload["MISC"] == [
        "vehicle_type_code:VEHTYPE_V",
        '(lot_make_desc:"TOYO" OR manufacturer_make_desc:"TOYO") OR (lot_make_desc:"TOYOTA" OR manufacturer_make_desc:"TOYOTA")',
        'lot_model_desc:"CAMRY" OR lot_model_group:"CAMRY" OR manufacturer_model_desc:"CAMRY"',
    ]


def test_search_request_builds_external_copart_url() -> None:
    request = SearchRequest(
        make="Ford",
        model="Mustang Mach-E",
        year_from=2025,
        year_to=2027,
        drive_type="all_wheel_drive",
        primary_damage="hail",
        title_type="salvage_title",
        fuel_type="electric",
        lot_condition="run_and_drive",
        odometer_range="under_25000",
    )

    url = request.to_external_url()
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    payload = json.loads(params["searchCriteria"][0])

    assert f"{parsed.scheme}://{parsed.netloc}{parsed.path}" == "https://www.copart.com/lotSearchResults"
    assert params["free"] == ["true"]
    assert params["displayStr"] == ["FORD MUSTANG MACH-E 2025-2027"]
    assert "qId" in params
    assert payload["filter"] == {
        "YEAR": ["lot_year:[2025 TO 2027]"],
        "MAKE": ['lot_make_desc:"FORD"'],
        "MODL": ['lot_model_desc:"MUSTANG MACH-E"'],
        "DRIV": ['drive:"ALL WHEEL DRIVE"'],
        "DMG": ["damage_type_code:DAMAGECODE_HL"],
        "TITL": ["title_group_code:TITLEGROUP_S"],
        "FUEL": ['fuel_type_desc:"ELECTRIC"'],
        "COND": ["lot_condition_code:CERT-D"],
        "ODM": ["odometer_reading_received:[* TO 25000]"],
    }


def test_search_request_builds_direct_lot_url_for_lot_number() -> None:
    request = SearchRequest(lot_number=" 123-456-78 ")

    assert request.to_external_url() == "https://www.copart.com/lot/12345678"
