from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys

import httpx
import mongomock


ROOT = Path(__file__).resolve().parents[2] / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from cartrap.config import Settings
from cartrap.modules.copart_provider.client import CopartHttpClient
from cartrap.modules.copart_provider.service import CopartProvider
from cartrap.modules.monitoring.service import MonitoringService
from cartrap.modules.search.catalog_refresh import SearchCatalogRefreshJob
from cartrap.modules.search.schemas import SearchRequest
from cartrap.modules.search.service import SearchService
from cartrap.modules.watchlist.service import WatchlistService


def make_gateway_settings() -> Settings:
    return Settings(
        ENVIRONMENT="test",
        MONGO_URI="mongodb://unused",
        MONGO_DB="cartrap_test",
        COPART_GATEWAY_BASE_URL="https://gateway.example.com",
        COPART_GATEWAY_TOKEN="gateway-secret",
        COPART_API_DEVICE_NAME="iPhone 15 Pro Max",
        COPART_API_D_TOKEN="token-123",
        COPART_API_COOKIE="SessionID=abc",
        COPART_API_SITECODE="CPRTUS",
    )


def make_gateway_provider(handler) -> CopartProvider:
    return CopartProvider(
        client=CopartHttpClient(
            settings=make_gateway_settings(),
            transport=httpx.MockTransport(handler),
        )
    )


SEARCH_RESPONSE = {
    "response": {
        "numFound": 1,
        "docs": [
            {
                "lot_number": 99251295,
                "lot_desc": "2025 FORD MUSTANG MACH-E PREMIUM",
                "lot_thumbnail_image_path": "https://img.copart.com/99251295.jpg",
                "yard_name": "MI - DETROIT",
                "auction_host_name": "MI - DETROIT",
                "auction_date_utc": "2026-03-20T14:00:00Z",
                "current_high_bid": 0,
                "currency_code": "USD",
                "status": "UPCOMING",
            }
        ],
    }
}

LOT_DETAILS_INITIAL = {
    "lotDetails": {
        "lotNumber": 76880725,
        "lotDescription": "2025 FORD MUSTANG MACH-E GT",
        "lotImages": [
            {"url": "https://img.copart.com/76880725-detail-1.jpg"},
        ],
        "odometer": {"formattedValue": "12,345 ACTUAL"},
        "primaryDamage": "FRONT END",
        "estRetailValue": 36500,
        "keys": "yes",
        "driveTrain": "AWD",
        "highlights": [{"label": "Run and Drive"}],
        "encryptedVIN": "VnQsUz1aMTpFPlxdCQcFAwU=",
        "saleStatus": "UPCOMING",
        "saleDate": "2026-03-20T17:00:00Z",
        "currentBid": 275,
        "buyTodayBid": 0,
        "currencyCode": "USD",
    }
}

LOT_DETAILS_CHANGED = {
    "lotDetails": {
        "lotNumber": 76880725,
        "lotDescription": "2025 FORD MUSTANG MACH-E GT",
        "lotImages": [
            {"url": "https://img.copart.com/76880725-detail-1.jpg"},
            {"url": "https://img.copart.com/76880725-detail-2.jpg"},
        ],
        "odometer": {"formattedValue": "12,678 ACTUAL"},
        "primaryDamage": "REAR END",
        "estRetailValue": 37250,
        "keys": "yes",
        "driveTrain": "AWD",
        "highlights": [{"label": "Enhanced Vehicles"}],
        "encryptedVIN": "VnQsUz1aMTpFPlxdCQcFAwU=",
        "saleStatus": "LIVE",
        "saleDate": "2026-03-20T17:00:00Z",
        "currentBid": 600,
        "buyTodayBid": 0,
        "currencyCode": "USD",
    }
}

KEYWORDS_RESPONSE = {
    "ford": {
        "text": "manufacturer_make_desc",
        "filterQuery": 'lot_make_desc:"FORD" OR manufacturer_make_desc:"FORD"',
        "type": "MAKE_MODEL",
    },
    "mustangmache": {
        "text": "manufacturer_model_desc",
        "filterQuery": 'lot_model_desc:"MUSTANG MACH-E" OR manufacturer_model_desc:"MUSTANG MACH-E"',
        "type": "MAKE_MODEL",
    },
    "2026": {
        "text": "2026",
        "filterQuery": 'lot_year:"2026"',
        "type": "YEAR",
    },
}


def test_search_service_supports_gateway_backed_raw_search_response() -> None:
    captured_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_urls.append(str(request.url))
        return httpx.Response(200, json=SEARCH_RESPONSE)

    database = mongomock.MongoClient(tz_aware=True)["cartrap_test"]
    service = SearchService(database, provider_factory=lambda: make_gateway_provider(handler))

    result = service.search(SearchRequest(make="Ford", model="Mustang Mach-E", year_from=2025, year_to=2027))

    assert result["total_results"] == 1
    assert result["results"][0]["lot_number"] == "99251295"
    assert captured_urls == ["https://gateway.example.com/v1/search"]


def test_watchlist_and_monitoring_support_gateway_backed_raw_lot_details() -> None:
    add_urls: list[str] = []
    poll_urls: list[str] = []

    def initial_handler(request: httpx.Request) -> httpx.Response:
        add_urls.append(str(request.url))
        return httpx.Response(200, json=LOT_DETAILS_INITIAL)

    def changed_handler(request: httpx.Request) -> httpx.Response:
        poll_urls.append(str(request.url))
        return httpx.Response(200, json=LOT_DETAILS_CHANGED)

    database = mongomock.MongoClient(tz_aware=True)["cartrap_test"]
    watchlist_service = WatchlistService(database, provider_factory=lambda: make_gateway_provider(initial_handler))
    created = watchlist_service.add_tracked_lot({"id": "user-1"}, "https://www.copart.com/lot/76880725")

    monitoring_service = MonitoringService(database, provider_factory=lambda: make_gateway_provider(changed_handler))
    result = monitoring_service.poll_due_lots(now=datetime(2026, 3, 20, 16, 30, tzinfo=timezone.utc))

    assert result["processed"] == 1
    assert result["updated"] == 1
    assert result["failed"] == 0
    stored = database["tracked_lots"].find_one({"lot_number": "76880725"})
    assert stored["status"] == "live"
    assert stored["primary_damage"] == "REAR END"
    assert stored["current_bid"] == 600.0
    assert add_urls == ["https://gateway.example.com/v1/lot-details"]
    assert poll_urls == ["https://gateway.example.com/v1/lot-details"]


def test_saved_search_count_supports_gateway_backed_raw_count_response() -> None:
    captured_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_urls.append(str(request.url))
        return httpx.Response(200, json={"response": {"numFound": 11}})

    database = mongomock.MongoClient(tz_aware=True)["cartrap_test"]
    service = SearchService(database, provider_factory=lambda: make_gateway_provider(handler))

    result = service.fetch_result_count(SearchRequest(make="Ford"))

    assert result == {"result_count": 11, "etag": None, "not_modified": False}
    assert captured_urls == ["https://gateway.example.com/v1/search-count"]


def test_catalog_refresh_job_supports_gateway_backed_search_keywords() -> None:
    captured_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_urls.append(str(request.url))
        return httpx.Response(200, json=KEYWORDS_RESPONSE)

    job = SearchCatalogRefreshJob(
        provider_factory=lambda: make_gateway_provider(handler),
        model_fetcher=lambda make_name: ["Mustang Mach-E"] if make_name == "FORD" else [],
    )

    catalog = job.refresh()

    assert catalog["summary"]["make_count"] == 1
    assert catalog["summary"]["model_count"] == 1
    assert catalog["years"] == [2026]
    assert captured_urls == ["https://gateway.example.com/v1/search-keywords"]
