from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys

import mongomock


ROOT = Path(__file__).resolve().parents[2] / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from cartrap.modules.provider_connections.repository import ProviderConnectionRepository


def test_repository_upserts_connection_and_replaces_existing_active_record() -> None:
    database = mongomock.MongoClient(tz_aware=True)["cartrap_test"]
    repository = ProviderConnectionRepository(database)
    repository.ensure_indexes()
    now = datetime(2026, 3, 24, 16, 0, tzinfo=timezone.utc)

    first = repository.upsert_connection(
        "user-1",
        "copart",
        {
            "status": "connected",
            "account_label": "first@example.com",
            "encrypted_session_bundle": "bundle-1",
            "encrypted_session_bundle_key_version": "v1",
            "bundle_captured_at": now,
            "bundle_expires_at": now,
            "bundle_version": 1,
            "updated_at": now,
        },
    )
    second = repository.upsert_connection(
        "user-1",
        "copart",
        {
            "status": "expiring",
            "account_label": "second@example.com",
            "encrypted_session_bundle": "bundle-2",
            "encrypted_session_bundle_key_version": "v1",
            "bundle_captured_at": now,
            "bundle_expires_at": now,
            "bundle_version": 1,
            "updated_at": now,
        },
    )

    assert first["_id"] == second["_id"]
    assert repository.provider_connections.count_documents({"owner_user_id": "user-1", "provider": "copart"}) == 1
    assert repository.find_by_user_and_provider("user-1", "copart")["account_label"] == "second@example.com"


def test_repository_disconnect_clears_ciphertext_and_resets_bundle_version() -> None:
    database = mongomock.MongoClient(tz_aware=True)["cartrap_test"]
    repository = ProviderConnectionRepository(database)
    repository.ensure_indexes()
    now = datetime(2026, 3, 24, 16, 5, tzinfo=timezone.utc)
    created = repository.upsert_connection(
        "user-2",
        "copart",
        {
            "status": "connected",
            "account_label": "owner@example.com",
            "encrypted_session_bundle": "bundle-1",
            "encrypted_session_bundle_key_version": "v1",
            "bundle_captured_at": now,
            "bundle_expires_at": now,
            "bundle_version": 4,
            "updated_at": now,
        },
    )

    disconnected = repository.disconnect_connection(str(created["_id"]), disconnected_at=now, updated_at=now)

    assert disconnected is not None
    assert disconnected["status"] == "disconnected"
    assert disconnected["encrypted_session_bundle"] is None
    assert disconnected["bundle_version"] == 1


def test_repository_compare_and_swap_bundle_rejects_stale_bundle_version() -> None:
    database = mongomock.MongoClient(tz_aware=True)["cartrap_test"]
    repository = ProviderConnectionRepository(database)
    repository.ensure_indexes()
    now = datetime(2026, 3, 24, 16, 10, tzinfo=timezone.utc)
    created = repository.upsert_connection(
        "user-3",
        "copart",
        {
            "status": "connected",
            "account_label": "owner@example.com",
            "encrypted_session_bundle": "bundle-1",
            "encrypted_session_bundle_key_version": "v1",
            "bundle_captured_at": now,
            "bundle_expires_at": now,
            "bundle_version": 2,
            "updated_at": now,
        },
    )

    stale = repository.compare_and_swap_bundle(
        str(created["_id"]),
        expected_bundle_version=1,
        encrypted_session_bundle="bundle-stale",
        encrypted_session_bundle_key_version="v1",
        bundle_captured_at=now,
        bundle_expires_at=now,
        updated_at=now,
        status="connected",
        last_verified_at=now,
        last_used_at=now,
    )
    fresh = repository.compare_and_swap_bundle(
        str(created["_id"]),
        expected_bundle_version=2,
        encrypted_session_bundle="bundle-2",
        encrypted_session_bundle_key_version="v1",
        bundle_captured_at=now,
        bundle_expires_at=now,
        updated_at=now,
        status="connected",
        last_verified_at=now,
        last_used_at=now,
    )

    assert stale is None
    assert fresh is not None
    assert fresh["encrypted_session_bundle"] == "bundle-2"
    assert fresh["bundle_version"] == 3
