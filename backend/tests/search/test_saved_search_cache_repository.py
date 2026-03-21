from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys

from bson import ObjectId
import mongomock


ROOT = Path(__file__).resolve().parents[2] / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from cartrap.modules.search.repository import SavedSearchRepository
from cartrap.modules.search.schemas import SavedSearchResponse, SavedSearchViewResponse
from cartrap.modules.search.service import SearchService


def _build_saved_search_document(owner_user_id: str = "user-1") -> dict:
    now = datetime(2026, 3, 16, 14, 0, tzinfo=timezone.utc)
    return {
        "_id": ObjectId(),
        "owner_user_id": owner_user_id,
        "label": "FORD MUSTANG MACH-E 2025-2027",
        "criteria": {
            "make": "FORD",
            "model": "MUSTANG MACH-E",
            "year_from": 2025,
            "year_to": 2027,
        },
        "result_count": 2,
        "search_etag": '"etag-1"',
        "criteria_key": '{"make":"FORD"}',
        "last_checked_at": now,
        "created_at": now,
        "updated_at": now,
    }


def _build_cached_results() -> list[dict]:
    return [
        {
            "lot_number": "12345678",
            "title": "2025 FORD MUSTANG MACH-E PREMIUM",
            "url": "https://www.copart.com/lot/12345678",
            "thumbnail_url": "https://img.copart.com/12345678.jpg",
            "location": "CA - SACRAMENTO",
            "sale_date": datetime(2026, 3, 20, 17, 0, tzinfo=timezone.utc),
            "current_bid": 4200.0,
            "currency": "USD",
            "status": "live",
        },
        {
            "lot_number": "87654321",
            "title": "2026 FORD MUSTANG MACH-E SELECT",
            "url": "https://www.copart.com/lot/87654321",
            "thumbnail_url": None,
            "location": "TX - DALLAS",
            "sale_date": datetime(2026, 3, 21, 18, 30, tzinfo=timezone.utc),
            "current_bid": 5100.0,
            "currency": "USD",
            "status": "upcoming",
        },
    ]


def test_saved_search_cache_upsert_and_lookup_are_owner_scoped() -> None:
    database = mongomock.MongoClient(tz_aware=True)["cartrap_test"]
    repository = SavedSearchRepository(database)
    repository.ensure_indexes()
    saved_search = _build_saved_search_document()
    database["saved_searches"].insert_one(saved_search)
    synced_at = datetime(2026, 3, 16, 14, 5, tzinfo=timezone.utc)

    stored_cache = repository.upsert_saved_search_cache(
        str(saved_search["_id"]),
        "user-1",
        results=_build_cached_results(),
        result_count=2,
        new_lot_numbers=["12345678", "87654321", "12345678"],
        last_synced_at=synced_at,
    )

    found_cache = repository.find_saved_search_cache_by_id_for_owner(str(saved_search["_id"]), "user-1")
    other_owner_cache = repository.find_saved_search_cache_by_id_for_owner(str(saved_search["_id"]), "user-2")
    listed_caches = repository.list_saved_search_caches_for_owner("user-1", [str(saved_search["_id"])])

    assert stored_cache["saved_search_id"] == saved_search["_id"]
    assert stored_cache["new_lot_numbers"] == ["12345678", "87654321"]
    assert found_cache is not None
    assert found_cache["result_count"] == 2
    assert found_cache["last_synced_at"] == synced_at
    assert other_owner_cache is None
    assert len(listed_caches) == 1
    assert listed_caches[0]["saved_search_id"] == saved_search["_id"]


def test_mark_saved_search_cache_viewed_clears_new_markers_and_sets_seen_at() -> None:
    database = mongomock.MongoClient(tz_aware=True)["cartrap_test"]
    repository = SavedSearchRepository(database)
    repository.ensure_indexes()
    saved_search = _build_saved_search_document()
    database["saved_searches"].insert_one(saved_search)
    repository.upsert_saved_search_cache(
        str(saved_search["_id"]),
        "user-1",
        results=_build_cached_results(),
        result_count=2,
        new_lot_numbers=["12345678"],
        last_synced_at=datetime(2026, 3, 16, 14, 5, tzinfo=timezone.utc),
    )
    viewed_at = datetime(2026, 3, 16, 14, 10, tzinfo=timezone.utc)

    updated_cache = repository.mark_saved_search_cache_viewed(
        str(saved_search["_id"]),
        "user-1",
        seen_at=viewed_at,
    )

    assert updated_cache is not None
    assert updated_cache["new_lot_numbers"] == ["12345678"]
    assert updated_cache.get("seen_at") is None
    persisted = repository.find_saved_search_cache_by_id_for_owner(str(saved_search["_id"]), "user-1")
    assert persisted is not None
    assert persisted["results"][0]["lot_number"] == "12345678"
    assert persisted["new_lot_numbers"] == []
    assert persisted["seen_at"] == viewed_at
    assert repository.mark_saved_search_cache_viewed(str(saved_search["_id"]), "user-2", seen_at=viewed_at) is None


def test_saved_search_cache_serialization_exposes_metadata_and_new_flags() -> None:
    database = mongomock.MongoClient(tz_aware=True)["cartrap_test"]
    service = SearchService(database)
    saved_search = _build_saved_search_document()
    cache_document = {
        "_id": ObjectId(),
        "saved_search_id": saved_search["_id"],
        "owner_user_id": "user-1",
        "results": _build_cached_results(),
        "result_count": 2,
        "new_lot_numbers": ["87654321"],
        "last_synced_at": datetime(2026, 3, 16, 14, 5, tzinfo=timezone.utc),
        "seen_at": datetime(2026, 3, 16, 14, 2, tzinfo=timezone.utc),
        "created_at": datetime(2026, 3, 16, 14, 1, tzinfo=timezone.utc),
        "updated_at": datetime(2026, 3, 16, 14, 5, tzinfo=timezone.utc),
    }

    serialized_saved_search = service.serialize_saved_search(saved_search, cache_document=cache_document)
    serialized_view = service.serialize_saved_search_cache_view(saved_search, cache_document)

    saved_search_response = SavedSearchResponse.model_validate(serialized_saved_search)
    view_response = SavedSearchViewResponse.model_validate(serialized_view)

    assert saved_search_response.cached_result_count == 2
    assert saved_search_response.new_count == 1
    assert saved_search_response.last_synced_at == cache_document["last_synced_at"]
    assert view_response.cached_result_count == 2
    assert view_response.new_count == 1
    assert view_response.results[0].is_new is False
    assert view_response.results[1].is_new is True


def test_delete_saved_search_removes_associated_cache() -> None:
    database = mongomock.MongoClient(tz_aware=True)["cartrap_test"]
    repository = SavedSearchRepository(database)
    repository.ensure_indexes()
    saved_search = _build_saved_search_document()
    database["saved_searches"].insert_one(saved_search)
    repository.upsert_saved_search_cache(
        str(saved_search["_id"]),
        "user-1",
        results=_build_cached_results(),
        result_count=2,
        new_lot_numbers=[],
        last_synced_at=datetime(2026, 3, 16, 14, 5, tzinfo=timezone.utc),
    )

    repository.delete_saved_search(str(saved_search["_id"]))

    assert database["saved_searches"].find_one({"_id": saved_search["_id"]}) is None
    assert database["saved_search_results_cache"].find_one({"saved_search_id": saved_search["_id"]}) is None
