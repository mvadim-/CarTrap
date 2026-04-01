from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

def test_admin_can_filter_sort_and_paginate_user_directory(client: TestClient, create_user, admin_headers) -> None:
    now = datetime(2026, 4, 1, 12, 0, tzinfo=timezone.utc)

    with client:
        database = client.app.state.mongo.database
        alpha_user_id = create_user(
            email="alpha@example.com",
            created_at=now - timedelta(days=10),
            last_login_at=now - timedelta(hours=2),
        )
        bravo_user_id = create_user(
            email="bravo@example.com",
            created_at=now - timedelta(days=5),
            status="blocked",
        )
        charlie_user_id = create_user(
            email="charlie@example.com",
            created_at=now - timedelta(days=1),
            last_login_at=now - timedelta(days=20),
        )

        database["provider_connections"].insert_many(
            [
                {
                    "owner_user_id": alpha_user_id,
                    "provider": "copart",
                    "status": "connected",
                    "account_label": "alpha-copart@example.com",
                    "created_at": now - timedelta(days=3),
                    "updated_at": now - timedelta(hours=5),
                    "connected_at": now - timedelta(days=3),
                    "bundle_version": 1,
                    "encrypted_session_bundle": "bundle",
                    "encrypted_session_bundle_key_version": "v1",
                    "bundle_captured_at": now - timedelta(days=3),
                    "bundle_expires_at": now + timedelta(days=1),
                },
                {
                    "owner_user_id": bravo_user_id,
                    "provider": "iaai",
                    "status": "reconnect_required",
                    "account_label": "bravo-iaai@example.com",
                    "created_at": now - timedelta(days=3),
                    "updated_at": now - timedelta(hours=6),
                    "connected_at": now - timedelta(days=3),
                    "bundle_version": 1,
                    "encrypted_session_bundle": None,
                    "encrypted_session_bundle_key_version": None,
                    "bundle_captured_at": None,
                    "bundle_expires_at": None,
                },
            ]
        )
        database["saved_searches"].insert_many(
            [
                {
                    "owner_user_id": alpha_user_id,
                    "label": "Alpha Search",
                    "criteria": {"providers": ["copart"], "make": "FORD", "model": "F-150"},
                    "created_at": now - timedelta(days=2),
                    "updated_at": now - timedelta(days=2),
                },
                {
                    "owner_user_id": charlie_user_id,
                    "label": "Charlie Search",
                    "criteria": {"providers": ["iaai"], "make": "TESLA", "model": "MODEL 3"},
                    "created_at": now - timedelta(days=1),
                    "updated_at": now - timedelta(days=1),
                },
            ]
        )
        database["tracked_lots"].insert_many(
            [
                {
                    "owner_user_id": alpha_user_id,
                    "provider": "copart",
                    "provider_lot_id": "111",
                    "lot_key": "copart:111",
                    "auction_label": "Copart",
                    "lot_number": "111",
                    "title": "Alpha Lot",
                    "status": "live",
                    "raw_status": "Live",
                    "currency": "USD",
                    "last_checked_at": now - timedelta(hours=2),
                    "created_at": now - timedelta(days=2),
                    "updated_at": now - timedelta(hours=2),
                    "has_unseen_update": False,
                },
                {
                    "owner_user_id": bravo_user_id,
                    "provider": "iaai",
                    "provider_lot_id": "222",
                    "lot_key": "iaai:222",
                    "auction_label": "IAAI",
                    "lot_number": "222",
                    "title": "Bravo Lot",
                    "status": "pending",
                    "raw_status": "Pending",
                    "currency": "USD",
                    "last_checked_at": now - timedelta(days=8),
                    "created_at": now - timedelta(days=4),
                    "updated_at": now - timedelta(days=1),
                    "has_unseen_update": True,
                },
            ]
        )
        database["push_subscriptions"].insert_one(
            {
                "owner_user_id": alpha_user_id,
                "endpoint": "https://push.example.com/alpha",
                "user_agent": "UnitTest Browser",
                "created_at": now - timedelta(days=1),
                "updated_at": now - timedelta(hours=1),
            }
        )
        database["invites"].insert_one(
            {
                "email": "bravo@example.com",
                "token": "bravo-pending",
                "status": "pending",
                "expires_at": now + timedelta(hours=2),
                "accepted_at": None,
                "revoked_at": None,
                "created_at": now - timedelta(hours=1),
                "created_by": "bootstrap-admin",
            }
        )

        reconnect_only = client.get(
            "/api/admin/users",
            params={"provider_state": "reconnect_required"},
            headers=admin_headers(),
        )
        unseen_updates = client.get(
            "/api/admin/users",
            params={"watchlist_state": "unseen_updates"},
            headers=admin_headers(),
        )
        no_push = client.get(
            "/api/admin/users",
            params={"push_state": "no_push", "sort": "email_asc", "page": 1, "page_size": 2},
            headers=admin_headers(),
        )
        page_two = client.get(
            "/api/admin/users",
            params={"sort": "email_asc", "page": 2, "page_size": 2},
            headers=admin_headers(),
        )

    assert reconnect_only.status_code == 200
    reconnect_rows = reconnect_only.json()["items"]
    assert [row["email"] for row in reconnect_rows] == ["bravo@example.com"]
    assert reconnect_rows[0]["flags"]["has_reconnect_required_provider"] is True

    assert unseen_updates.status_code == 200
    unseen_rows = unseen_updates.json()["items"]
    assert [row["email"] for row in unseen_rows] == ["bravo@example.com"]
    assert unseen_rows[0]["flags"]["has_unseen_watchlist_updates"] is True

    assert no_push.status_code == 200
    no_push_payload = no_push.json()
    assert no_push_payload["total"] == 3
    assert [row["email"] for row in no_push_payload["items"]] == ["admin@example.com", "bravo@example.com"]

    assert page_two.status_code == 200
    page_two_payload = page_two.json()
    assert page_two_payload["page"] == 2
    assert [row["email"] for row in page_two_payload["items"]] == ["bravo@example.com", "charlie@example.com"]


def test_admin_user_detail_returns_aggregate_sections(client: TestClient, create_user, admin_headers) -> None:
    now = datetime(2026, 4, 1, 12, 0, tzinfo=timezone.utc)

    with client:
        database = client.app.state.mongo.database
        user_id = create_user(
            email="detail-user@example.com",
            created_at=now - timedelta(days=7),
            last_login_at=now - timedelta(hours=3),
        )
        saved_search_id = database["saved_searches"].insert_one(
            {
                "owner_user_id": user_id,
                "label": "Detail Search",
                "criteria": {"providers": ["copart", "iaai"], "make": "BMW", "model": "X5"},
                "result_count": 4,
                "created_at": now - timedelta(days=2),
                "updated_at": now - timedelta(days=2),
                "last_refresh_attempted_at": now - timedelta(hours=2),
                "last_refresh_succeeded_at": now - timedelta(hours=2),
            }
        ).inserted_id
        database["saved_search_results_cache"].insert_one(
            {
                "saved_search_id": saved_search_id,
                "owner_user_id": user_id,
                "result_count": 4,
                "new_lot_keys": ["copart:123"],
                "last_synced_at": now - timedelta(hours=2),
                "created_at": now - timedelta(days=2),
                "updated_at": now - timedelta(hours=2),
            }
        )
        tracked_lot_id = database["tracked_lots"].insert_one(
            {
                "owner_user_id": user_id,
                "provider": "copart",
                "provider_lot_id": "123",
                "lot_key": "copart:123",
                "auction_label": "Copart",
                "lot_number": "123",
                "title": "Detail Lot",
                "status": "live",
                "raw_status": "Live",
                "currency": "USD",
                "last_checked_at": now - timedelta(hours=2),
                "created_at": now - timedelta(days=1),
                "updated_at": now - timedelta(hours=2),
                "has_unseen_update": True,
            }
        ).inserted_id
        database["lot_snapshots"].insert_one(
            {
                "tracked_lot_id": str(tracked_lot_id),
                "provider": "copart",
                "provider_lot_id": "123",
                "lot_key": "copart:123",
                "lot_number": "123",
                "status": "live",
                "raw_status": "Live",
                "currency": "USD",
                "detected_at": now - timedelta(hours=1),
            }
        )
        database["provider_connections"].insert_one(
            {
                "owner_user_id": user_id,
                "provider": "copart",
                "status": "connected",
                "account_label": "detail-copart@example.com",
                "created_at": now - timedelta(days=5),
                "updated_at": now - timedelta(hours=5),
                "connected_at": now - timedelta(days=5),
                "bundle_version": 2,
                "encrypted_session_bundle": "bundle",
                "encrypted_session_bundle_key_version": "v1",
                "bundle_captured_at": now - timedelta(days=5),
                "bundle_expires_at": now + timedelta(days=1),
            }
        )
        database["push_subscriptions"].insert_one(
            {
                "owner_user_id": user_id,
                "endpoint": "https://push.example.com/detail",
                "user_agent": "UnitTest Browser",
                "created_at": now - timedelta(days=1),
                "updated_at": now - timedelta(hours=1),
            }
        )
        database["invites"].insert_many(
            [
                {
                    "email": "detail-user@example.com",
                    "token": "accepted-token",
                    "status": "accepted",
                    "expires_at": now - timedelta(days=5),
                    "accepted_at": now - timedelta(days=5),
                    "revoked_at": None,
                    "created_at": now - timedelta(days=6),
                    "created_by": "bootstrap-admin",
                },
                {
                    "email": "detail-user@example.com",
                    "token": "pending-token",
                    "status": "pending",
                    "expires_at": now + timedelta(days=1),
                    "accepted_at": None,
                    "revoked_at": None,
                    "created_at": now - timedelta(hours=6),
                    "created_by": "bootstrap-admin",
                },
            ]
        )
        detail_response = client.get(f"/api/admin/users/{user_id}", headers=admin_headers())

    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["account"]["email"] == "detail-user@example.com"
    assert detail["counts"]["saved_searches"] == 1
    assert len(detail["invites"]) == 2
    assert len(detail["provider_connections"]) == 1
    assert detail["saved_searches"][0]["new_count"] == 1
    assert detail["tracked_lots"][0]["lot_number"] == "123"
    assert detail["push_subscriptions"][0]["endpoint"] == "https://push.example.com/detail"
    assert detail["recent_activity"]["has_unseen_watchlist_updates"] is True
    assert detail["danger_zone"]["lot_snapshots"] == 1
