from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

from bson import ObjectId
import mongomock


ROOT = Path(__file__).resolve().parents[2] / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from cartrap.modules.copart_provider.models import CopartSearchPage
from cartrap.modules.search.schemas import SavedSearchCreateRequest
from cartrap.modules.search.service import SearchService


class FakeProvider:
    def __init__(self, num_found_sequence: list[int], should_fail: bool = False) -> None:
        self._num_found_sequence = num_found_sequence
        self._should_fail = should_fail
        self.search_payloads: list[dict] = []
        self._index = 0

    def search_lots(self, payload: dict) -> CopartSearchPage:
        if self._should_fail:
            raise RuntimeError("upstream failed")
        self.search_payloads.append(payload)
        num_found = self._num_found_sequence[min(self._index, len(self._num_found_sequence) - 1)]
        self._index += 1
        return CopartSearchPage(results=[], num_found=num_found)

    def close(self) -> None:
        return None


class EtagAwareProvider:
    def __init__(self, *, not_modified: bool, etag: str | None, num_found: int | None = None) -> None:
        self._not_modified = not_modified
        self._etag = etag
        self._num_found = num_found
        self.calls: list[tuple[dict, str | None]] = []

    def fetch_search_count_conditional(self, payload: dict, etag: str | None = None):
        self.calls.append((payload, etag))
        return type(
            "SearchCountResult",
            (),
            {"num_found": self._num_found, "etag": self._etag, "not_modified": self._not_modified},
        )()

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


def test_saved_search_poll_sends_push_when_match_count_increases() -> None:
    database = mongomock.MongoClient(tz_aware=True)["cartrap_test"]
    notification_service = FakeNotificationService()
    provider = FakeProvider([6])
    service = SearchService(
        database,
        provider_factory=lambda: provider,
        notification_service=notification_service,
    )
    current_time = datetime(2026, 3, 13, 12, 0, tzinfo=timezone.utc)
    saved = service.save_search(
        {"id": "user-1"},
        SavedSearchCreateRequest(make="Ford", model="Mustang Mach-E", year_from=2025, year_to=2027, result_count=4),
    )["saved_search"]
    database["saved_searches"].update_one(
        {"_id": ObjectId(saved["id"])},
        {"$set": {"last_checked_at": current_time - timedelta(minutes=16)}},
    )

    result = service.poll_due_saved_searches(now=current_time)

    assert result["processed"] == 1
    assert result["updated"] == 1
    assert result["failed"] == 0
    assert result["notified"] == 1
    assert result["events"][0]["new_matches"] == 2
    assert notification_service.events[0]["search_title"] == "FORD MUSTANG MACH-E 2025-2027"
    stored = database["saved_searches"].find_one({"owner_user_id": "user-1"})
    assert stored["result_count"] == 6
    assert stored["last_checked_at"] == current_time


def test_saved_search_poll_updates_result_count_without_push_when_matches_drop() -> None:
    database = mongomock.MongoClient(tz_aware=True)["cartrap_test"]
    notification_service = FakeNotificationService()
    provider = FakeProvider([3])
    service = SearchService(
        database,
        provider_factory=lambda: provider,
        notification_service=notification_service,
    )
    current_time = datetime(2026, 3, 13, 12, 0, tzinfo=timezone.utc)
    saved = service.save_search(
        {"id": "user-2"},
        SavedSearchCreateRequest(make="Ford", model="Mustang Mach-E", result_count=5),
    )["saved_search"]
    database["saved_searches"].update_one(
        {"_id": ObjectId(saved["id"])},
        {"$set": {"last_checked_at": current_time - timedelta(minutes=16)}},
    )

    result = service.poll_due_saved_searches(now=current_time)

    assert result["processed"] == 1
    assert result["updated"] == 1
    assert result["notified"] == 0
    assert result["events"][0]["new_matches"] == 0
    assert notification_service.events == []
    stored = database["saved_searches"].find_one({"owner_user_id": "user-2"})
    assert stored["result_count"] == 3


def test_saved_search_poll_skips_recently_checked_searches() -> None:
    database = mongomock.MongoClient(tz_aware=True)["cartrap_test"]
    notification_service = FakeNotificationService()
    provider = FakeProvider([8])
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


def test_saved_search_poll_skips_heavy_refresh_when_search_etag_is_not_modified() -> None:
    database = mongomock.MongoClient(tz_aware=True)["cartrap_test"]
    notification_service = FakeNotificationService()
    provider = EtagAwareProvider(not_modified=True, etag="\"search-etag-2\"")
    service = SearchService(
        database,
        provider_factory=lambda: provider,
        notification_service=notification_service,
    )
    current_time = datetime(2026, 3, 13, 12, 0, tzinfo=timezone.utc)
    saved = service.save_search(
        {"id": "user-4"},
        SavedSearchCreateRequest(make="Ford", model="Mustang Mach-E", result_count=5),
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

    assert result == {
        "processed": 1,
        "updated": 0,
        "failed": 0,
        "notified": 0,
        "events": [],
    }
    assert provider.calls[0][1] == "\"search-etag-1\""
    stored = database["saved_searches"].find_one({"_id": ObjectId(saved["id"])})
    assert stored["search_etag"] == "\"search-etag-2\""
    assert stored["result_count"] == 5
    assert notification_service.events == []
