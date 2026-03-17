from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

from bson import ObjectId
import mongomock


ROOT = Path(__file__).resolve().parents[2] / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from cartrap.modules.copart_provider.errors import CopartGatewayUnavailableError
from cartrap.modules.copart_provider.models import CopartSearchPage, CopartSearchResult
from cartrap.modules.search.schemas import SavedSearchCreateRequest
from cartrap.modules.search.service import SearchService


class ConditionalSearchProvider:
    def __init__(
        self,
        *,
        not_modified: bool,
        etag: str | None,
        results: list[CopartSearchResult] | None = None,
        num_found: int | None = None,
        should_fail: bool = False,
    ) -> None:
        self._not_modified = not_modified
        self._etag = etag
        self._results = results or []
        self._num_found = len(self._results) if num_found is None else num_found
        self._should_fail = should_fail
        self.count_calls: list[tuple[dict, str | None]] = []
        self.search_payloads: list[dict] = []

    def fetch_search_count_conditional(self, payload: dict, etag: str | None = None):
        if self._should_fail:
            raise RuntimeError("upstream failed")
        self.count_calls.append((payload, etag))
        return type(
            "SearchCountResult",
            (),
            {"num_found": self._num_found, "etag": self._etag, "not_modified": self._not_modified},
        )()

    def search_lots(self, payload: dict) -> CopartSearchPage:
        if self._should_fail:
            raise RuntimeError("upstream failed")
        self.search_payloads.append(payload)
        page_number = int(payload.get("pageNumber", 1))
        return CopartSearchPage(results=self._results if page_number == 1 else [], num_found=self._num_found)

    def close(self) -> None:
        return None


class GatewayUnavailableProvider:
    def fetch_search_count_conditional(self, payload: dict, etag: str | None = None):
        del payload
        del etag
        raise CopartGatewayUnavailableError("gateway unavailable")

    def close(self) -> None:
        return None


class FakeNotificationService:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def send_saved_search_match_notification(self, event: dict) -> dict:
        self.events.append(event)
        return {
            "delivered": 1,
            "failed": 0,
            "removed": 0,
            "endpoints": ["https://push.example.test/subscriptions/1"],
        }


def _build_result(lot_number: str) -> CopartSearchResult:
    return CopartSearchResult(
        lot_number=lot_number,
        title=f"2025 FORD MUSTANG MACH-E {lot_number}",
        url=f"https://www.copart.com/lot/{lot_number}",
        thumbnail_url=f"https://img.copart.com/{lot_number}.jpg",
        location="CA - SACRAMENTO",
        sale_date=datetime(2026, 3, 20, 17, 0, tzinfo=timezone.utc),
        current_bid=4200.0,
        currency="USD",
        status="live",
    )


def _build_result_payload(lot_number: str) -> dict:
    return _build_result(lot_number).model_dump(mode="json")


def test_saved_search_poll_sends_push_when_new_lot_numbers_appear() -> None:
    database = mongomock.MongoClient(tz_aware=True)["cartrap_test"]
    notification_service = FakeNotificationService()
    provider = ConditionalSearchProvider(
        not_modified=False,
        etag="\"search-etag-2\"",
        results=[_build_result("11111111"), _build_result("22222222"), _build_result("33333333")],
        num_found=3,
    )
    service = SearchService(
        database,
        provider_factory=lambda: provider,
        notification_service=notification_service,
    )
    current_time = datetime(2026, 3, 13, 12, 0, tzinfo=timezone.utc)
    saved = service.save_search(
        {"id": "user-1"},
        SavedSearchCreateRequest(
            make="Ford",
            model="Mustang Mach-E",
            year_from=2025,
            year_to=2027,
            result_count=2,
            seed_results=[_build_result_payload("11111111"), _build_result_payload("22222222")],
        ),
    )["saved_search"]
    database["saved_searches"].update_one(
        {"_id": ObjectId(saved["id"])},
        {"$set": {"last_checked_at": current_time - timedelta(minutes=16), "search_etag": "\"search-etag-1\""}},
    )
    database["saved_search_results_cache"].update_one(
        {"saved_search_id": ObjectId(saved["id"])},
        {"$set": {"new_lot_numbers": ["11111111"], "seen_at": None}},
    )

    result = service.poll_due_saved_searches(now=current_time)

    assert result["processed"] == 1
    assert result["updated"] == 1
    assert result["failed"] == 0
    assert result["notified"] == 1
    assert result["events"][0]["new_matches"] == 1
    assert result["events"][0]["new_lot_numbers"] == ["33333333"]
    assert result["events"][0]["cached_new_count"] == 2
    assert notification_service.events[0]["search_title"] == "FORD MUSTANG MACH-E 2025-2027"
    assert notification_service.events[0]["new_matches"] == 1
    stored = database["saved_searches"].find_one({"owner_user_id": "user-1"})
    assert stored["result_count"] == 3
    assert stored["search_etag"] == "\"search-etag-2\""
    assert stored["last_checked_at"] == current_time
    cache_document = database["saved_search_results_cache"].find_one({"saved_search_id": ObjectId(saved["id"])})
    assert cache_document is not None
    assert cache_document["new_lot_numbers"] == ["11111111", "33333333"]
    assert cache_document["result_count"] == 3
    assert cache_document["last_synced_at"] == current_time
    assert len(provider.search_payloads) == 1


def test_saved_search_poll_updates_cache_without_push_when_results_change_but_no_new_lot_numbers() -> None:
    database = mongomock.MongoClient(tz_aware=True)["cartrap_test"]
    notification_service = FakeNotificationService()
    provider = ConditionalSearchProvider(
        not_modified=False,
        etag="\"search-etag-2\"",
        results=[_build_result("22222222"), _build_result("11111111")],
        num_found=2,
    )
    service = SearchService(
        database,
        provider_factory=lambda: provider,
        notification_service=notification_service,
    )
    current_time = datetime(2026, 3, 13, 12, 0, tzinfo=timezone.utc)
    saved = service.save_search(
        {"id": "user-2"},
        SavedSearchCreateRequest(
            make="Ford",
            model="Mustang Mach-E",
            result_count=2,
            seed_results=[_build_result_payload("11111111"), _build_result_payload("22222222")],
        ),
    )["saved_search"]
    database["saved_searches"].update_one(
        {"_id": ObjectId(saved["id"])},
        {"$set": {"last_checked_at": current_time - timedelta(minutes=16), "search_etag": "\"search-etag-1\""}},
    )
    database["saved_search_results_cache"].update_one(
        {"saved_search_id": ObjectId(saved["id"])},
        {"$set": {"new_lot_numbers": ["11111111"], "seen_at": None}},
    )

    result = service.poll_due_saved_searches(now=current_time)

    assert result["processed"] == 1
    assert result["updated"] == 1
    assert result["notified"] == 0
    assert result["events"][0]["new_matches"] == 0
    assert result["events"][0]["new_lot_numbers"] == []
    assert notification_service.events == []
    stored = database["saved_searches"].find_one({"owner_user_id": "user-2"})
    assert stored["result_count"] == 2
    assert stored["search_etag"] == "\"search-etag-2\""
    cache_document = database["saved_search_results_cache"].find_one({"saved_search_id": ObjectId(saved["id"])})
    assert cache_document is not None
    assert cache_document["new_lot_numbers"] == ["11111111"]
    assert len(provider.search_payloads) == 1


def test_saved_search_poll_skips_recently_checked_searches() -> None:
    database = mongomock.MongoClient(tz_aware=True)["cartrap_test"]
    notification_service = FakeNotificationService()
    provider = ConditionalSearchProvider(not_modified=False, etag="\"search-etag-1\"", results=[_build_result("11111111")])
    service = SearchService(
        database,
        provider_factory=lambda: provider,
        notification_service=notification_service,
    )
    current_time = datetime(2026, 3, 13, 12, 0, tzinfo=timezone.utc)
    service.save_search(
        {"id": "user-3"},
        SavedSearchCreateRequest(make="Ford", model="Mustang Mach-E", result_count=5),
    )

    result = service.poll_due_saved_searches(now=current_time)

    assert result == {
        "processed": 0,
        "updated": 0,
        "failed": 0,
        "notified": 0,
        "events": [],
    }
    assert provider.search_payloads == []


def test_saved_search_poll_uses_configured_interval() -> None:
    database = mongomock.MongoClient(tz_aware=True)["cartrap_test"]
    notification_service = FakeNotificationService()
    provider = ConditionalSearchProvider(not_modified=False, etag="\"search-etag-1\"", results=[_build_result("11111111")])
    service = SearchService(
        database,
        provider_factory=lambda: provider,
        notification_service=notification_service,
        saved_search_poll_interval_minutes=30,
    )
    current_time = datetime(2026, 3, 13, 12, 0, tzinfo=timezone.utc)
    saved = service.save_search(
        {"id": "user-interval"},
        SavedSearchCreateRequest(make="Ford", model="Mustang Mach-E", result_count=5),
    )["saved_search"]
    database["saved_searches"].update_one(
        {"_id": ObjectId(saved["id"])},
        {"$set": {"last_checked_at": current_time - timedelta(minutes=20)}},
    )

    result = service.poll_due_saved_searches(now=current_time)

    assert result == {
        "processed": 0,
        "updated": 0,
        "failed": 0,
        "notified": 0,
        "events": [],
    }
    assert provider.search_payloads == []


def test_saved_search_poll_backfills_missing_cache_even_when_search_etag_is_not_modified() -> None:
    database = mongomock.MongoClient(tz_aware=True)["cartrap_test"]
    notification_service = FakeNotificationService()
    provider = ConditionalSearchProvider(
        not_modified=True,
        etag="\"search-etag-2\"",
        results=[_build_result("11111111"), _build_result("22222222")],
        num_found=2,
    )
    service = SearchService(
        database,
        provider_factory=lambda: provider,
        notification_service=notification_service,
    )
    current_time = datetime(2026, 3, 13, 12, 0, tzinfo=timezone.utc)
    saved = service.save_search(
        {"id": "user-4"},
        SavedSearchCreateRequest(make="Ford", model="Mustang Mach-E", result_count=2),
    )["saved_search"]
    database["saved_searches"].update_one(
        {"_id": ObjectId(saved["id"])},
        {
            "$set": {
                "search_etag": "\"search-etag-1\"",
                "last_checked_at": current_time - timedelta(minutes=16),
            }
        },
    )

    result = service.poll_due_saved_searches(now=current_time)

    assert result["processed"] == 1
    assert result["updated"] == 1
    assert result["failed"] == 0
    assert result["notified"] == 0
    assert result["events"][0]["new_matches"] == 0
    assert provider.count_calls[0][1] == "\"search-etag-1\""
    stored = database["saved_searches"].find_one({"_id": ObjectId(saved["id"])})
    assert stored["search_etag"] == "\"search-etag-2\""
    assert stored["result_count"] == 2
    assert stored["last_checked_at"] == current_time
    cache_document = database["saved_search_results_cache"].find_one({"saved_search_id": ObjectId(saved["id"])})
    assert cache_document is not None
    assert cache_document["result_count"] == 2
    assert cache_document["new_lot_numbers"] == []
    assert cache_document["last_synced_at"] == current_time
    assert len(provider.search_payloads) == 1
    assert notification_service.events == []


def test_saved_search_poll_skips_heavy_refresh_when_search_etag_is_not_modified_and_cache_exists() -> None:
    database = mongomock.MongoClient(tz_aware=True)["cartrap_test"]
    notification_service = FakeNotificationService()
    provider = ConditionalSearchProvider(not_modified=True, etag="\"search-etag-2\"", results=[_build_result("11111111")], num_found=1)
    service = SearchService(
        database,
        provider_factory=lambda: provider,
        notification_service=notification_service,
    )
    current_time = datetime(2026, 3, 13, 12, 0, tzinfo=timezone.utc)
    saved = service.save_search(
        {"id": "user-44"},
        SavedSearchCreateRequest(
            make="Ford",
            model="Mustang Mach-E",
            result_count=1,
            seed_results=[_build_result_payload("11111111")],
        ),
    )["saved_search"]
    database["saved_searches"].update_one(
        {"_id": ObjectId(saved["id"])},
        {"$set": {"search_etag": "\"search-etag-1\"", "last_checked_at": current_time - timedelta(minutes=16)}},
    )

    result = service.poll_due_saved_searches(now=current_time)

    assert result == {
        "processed": 1,
        "updated": 0,
        "failed": 0,
        "notified": 0,
        "events": [],
    }
    assert provider.count_calls[0][1] == "\"search-etag-1\""
    assert provider.search_payloads == []
    stored = database["saved_searches"].find_one({"_id": ObjectId(saved["id"])})
    assert stored["search_etag"] == "\"search-etag-2\""
    assert stored["result_count"] == 1
    assert notification_service.events == []


def test_saved_search_poll_counts_gateway_failure_without_crashing_loop() -> None:
    database = mongomock.MongoClient(tz_aware=True)["cartrap_test"]
    notification_service = FakeNotificationService()
    service = SearchService(
        database,
        provider_factory=lambda: GatewayUnavailableProvider(),
        notification_service=notification_service,
    )
    current_time = datetime(2026, 3, 13, 12, 0, tzinfo=timezone.utc)
    saved = service.save_search(
        {"id": "user-5"},
        SavedSearchCreateRequest(make="Ford", model="Mustang Mach-E", result_count=5),
    )["saved_search"]
    database["saved_searches"].update_one(
        {"_id": ObjectId(saved["id"])},
        {"$set": {"last_checked_at": current_time - timedelta(minutes=16)}},
    )

    result = service.poll_due_saved_searches(now=current_time)

    assert result == {
        "processed": 1,
        "updated": 0,
        "failed": 1,
        "notified": 0,
        "events": [],
    }
    stored = database["saved_searches"].find_one({"_id": ObjectId(saved["id"])})
    assert stored["result_count"] == 5
    assert stored["last_checked_at"] == current_time - timedelta(minutes=16)
    assert notification_service.events == []
