from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

def test_admin_account_actions_update_user_state_and_guard_last_admin(client: TestClient, create_user, admin_headers) -> None:
    now = datetime(2026, 4, 1, 12, 0, tzinfo=timezone.utc)

    with client:
        target_user_id = create_user(
            email="managed-user@example.com",
            created_at=now - timedelta(days=2),
        )

        block_response = client.post(
            f"/api/admin/users/{target_user_id}/actions/block",
            json={},
            headers=admin_headers(),
        )
        unblock_response = client.post(
            f"/api/admin/users/{target_user_id}/actions/unblock",
            json={},
            headers=admin_headers(),
        )
        reset_password_response = client.post(
            f"/api/admin/users/{target_user_id}/actions/reset_password",
            json={},
            headers=admin_headers(),
        )
        promote_response = client.post(
            f"/api/admin/users/{target_user_id}/actions/promote",
            json={},
            headers=admin_headers(),
        )
        demote_response = client.post(
            f"/api/admin/users/{target_user_id}/actions/demote",
            json={},
            headers=admin_headers(),
        )
        admin_user = client.app.state.mongo.database["users"].find_one({"email": "admin@example.com"})
        last_admin_guard = client.post(
            f"/api/admin/users/{admin_user['_id']}/actions/demote",
            json={},
            headers=admin_headers(),
        )

    assert block_response.status_code == 200
    assert block_response.json()["user"]["status"] == "blocked"
    assert unblock_response.status_code == 200
    assert unblock_response.json()["user"]["status"] == "active"
    assert reset_password_response.status_code == 200
    assert reset_password_response.json()["generated_password"]
    assert promote_response.status_code == 200
    assert promote_response.json()["user"]["role"] == "admin"
    assert demote_response.status_code == 200
    assert demote_response.json()["user"]["role"] == "user"
    assert last_admin_guard.status_code == 409
    assert "last active admin" in last_admin_guard.json()["detail"]


def test_admin_resource_and_provider_actions_cleanup_owned_documents(client: TestClient, create_user, admin_headers) -> None:
    now = datetime(2026, 4, 1, 12, 0, tzinfo=timezone.utc)

    with client:
        database = client.app.state.mongo.database
        user_id = create_user(
            email="resource-user@example.com",
            created_at=now - timedelta(days=3),
        )
        saved_search_id = database["saved_searches"].insert_one(
            {
                "owner_user_id": user_id,
                "label": "Managed Search",
                "criteria": {"providers": ["copart"], "make": "FORD", "model": "ESCAPE"},
                "created_at": now - timedelta(days=2),
                "updated_at": now - timedelta(days=2),
            }
        ).inserted_id
        database["saved_search_results_cache"].insert_one(
            {
                "saved_search_id": saved_search_id,
                "owner_user_id": user_id,
                "result_count": 1,
                "new_lot_keys": [],
                "last_synced_at": now - timedelta(hours=1),
                "created_at": now - timedelta(days=2),
                "updated_at": now - timedelta(hours=1),
            }
        )
        tracked_lot_id = database["tracked_lots"].insert_one(
            {
                "owner_user_id": user_id,
                "provider": "iaai",
                "provider_lot_id": "9988",
                "lot_key": "iaai:9988",
                "auction_label": "IAAI",
                "lot_number": "9988",
                "title": "Managed Lot",
                "status": "pending",
                "raw_status": "Pending",
                "currency": "USD",
                "last_checked_at": now - timedelta(hours=3),
                "created_at": now - timedelta(days=2),
                "updated_at": now - timedelta(hours=3),
            }
        ).inserted_id
        database["lot_snapshots"].insert_one(
            {
                "tracked_lot_id": str(tracked_lot_id),
                "provider": "iaai",
                "provider_lot_id": "9988",
                "lot_key": "iaai:9988",
                "lot_number": "9988",
                "status": "pending",
                "raw_status": "Pending",
                "currency": "USD",
                "detected_at": now - timedelta(hours=2),
            }
        )
        provider_connection_id = database["provider_connections"].insert_one(
            {
                "owner_user_id": user_id,
                "provider": "iaai",
                "status": "connected",
                "account_label": "resource-iaai@example.com",
                "created_at": now - timedelta(days=2),
                "updated_at": now - timedelta(hours=4),
                "connected_at": now - timedelta(days=2),
                "bundle_version": 1,
                "encrypted_session_bundle": "bundle",
                "encrypted_session_bundle_key_version": "v1",
                "bundle_captured_at": now - timedelta(days=2),
                "bundle_expires_at": now + timedelta(days=1),
            }
        ).inserted_id
        push_subscription_id = database["push_subscriptions"].insert_one(
            {
                "owner_user_id": user_id,
                "endpoint": "https://push.example.com/resource",
                "user_agent": "UnitTest Browser",
                "created_at": now - timedelta(days=1),
                "updated_at": now - timedelta(hours=1),
            }
        ).inserted_id

        disconnect_response = client.post(
            f"/api/admin/users/{user_id}/actions/disconnect_provider",
            json={"provider": "iaai"},
            headers=admin_headers(),
        )
        delete_saved_search_response = client.post(
            f"/api/admin/users/{user_id}/actions/delete_saved_search",
            json={"resource_id": str(saved_search_id)},
            headers=admin_headers(),
        )
        purge_snapshots_response = client.post(
            f"/api/admin/users/{user_id}/actions/purge_snapshots",
            json={"resource_id": str(tracked_lot_id)},
            headers=admin_headers(),
        )
        delete_tracked_lot_response = client.post(
            f"/api/admin/users/{user_id}/actions/delete_tracked_lot",
            json={"resource_id": str(tracked_lot_id)},
            headers=admin_headers(),
        )
        delete_push_subscription_response = client.post(
            f"/api/admin/users/{user_id}/actions/delete_push_subscription",
            json={"resource_id": str(push_subscription_id)},
            headers=admin_headers(),
        )

        connection_after_disconnect = database["provider_connections"].find_one({"_id": provider_connection_id})
        saved_search_after_delete = database["saved_searches"].find_one({"_id": saved_search_id})
        cache_after_delete = database["saved_search_results_cache"].find_one({"saved_search_id": saved_search_id})
        tracked_lot_after_delete = database["tracked_lots"].find_one({"_id": tracked_lot_id})
        push_after_delete = database["push_subscriptions"].find_one({"_id": push_subscription_id})

    assert disconnect_response.status_code == 200
    assert connection_after_disconnect["status"] == "disconnected"
    assert delete_saved_search_response.status_code == 200
    assert saved_search_after_delete is None
    assert cache_after_delete is None
    assert purge_snapshots_response.status_code == 200
    assert purge_snapshots_response.json()["counts"]["lot_snapshots"] == 1
    assert delete_tracked_lot_response.status_code == 200
    assert tracked_lot_after_delete is None
    assert delete_push_subscription_response.status_code == 200
    assert push_after_delete is None


def test_delete_user_cascades_related_documents_and_regular_users_cannot_run_actions(client: TestClient, create_user, admin_headers) -> None:
    now = datetime(2026, 4, 1, 12, 0, tzinfo=timezone.utc)

    with client:
        database = client.app.state.mongo.database
        user_id = create_user(
            email="delete-me@example.com",
            created_at=now - timedelta(days=4),
        )
        database["invites"].insert_one(
            {
                "email": "delete-me@example.com",
                "token": "delete-me-invite",
                "status": "accepted",
                "expires_at": now - timedelta(days=3),
                "accepted_at": now - timedelta(days=3),
                "revoked_at": None,
                "created_at": now - timedelta(days=5),
                "created_by": "bootstrap-admin",
            }
        )
        saved_search_id = database["saved_searches"].insert_one(
            {
                "owner_user_id": user_id,
                "label": "Delete Search",
                "criteria": {"providers": ["copart"], "make": "FORD", "model": "EDGE"},
                "created_at": now - timedelta(days=2),
                "updated_at": now - timedelta(days=2),
            }
        ).inserted_id
        database["saved_search_results_cache"].insert_one(
            {
                "saved_search_id": saved_search_id,
                "owner_user_id": user_id,
                "result_count": 1,
                "new_lot_keys": [],
                "last_synced_at": now - timedelta(hours=1),
                "created_at": now - timedelta(days=2),
                "updated_at": now - timedelta(hours=1),
            }
        )
        tracked_lot_id = database["tracked_lots"].insert_one(
            {
                "owner_user_id": user_id,
                "provider": "copart",
                "provider_lot_id": "555",
                "lot_key": "copart:555",
                "auction_label": "Copart",
                "lot_number": "555",
                "title": "Delete Lot",
                "status": "live",
                "raw_status": "Live",
                "currency": "USD",
                "last_checked_at": now - timedelta(hours=2),
                "created_at": now - timedelta(days=2),
                "updated_at": now - timedelta(hours=2),
            }
        ).inserted_id
        database["lot_snapshots"].insert_one(
            {
                "tracked_lot_id": str(tracked_lot_id),
                "provider": "copart",
                "provider_lot_id": "555",
                "lot_key": "copart:555",
                "lot_number": "555",
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
                "account_label": "delete-copart@example.com",
                "created_at": now - timedelta(days=2),
                "updated_at": now - timedelta(hours=4),
                "connected_at": now - timedelta(days=2),
                "bundle_version": 1,
                "encrypted_session_bundle": "bundle",
                "encrypted_session_bundle_key_version": "v1",
                "bundle_captured_at": now - timedelta(days=2),
                "bundle_expires_at": now + timedelta(days=1),
            }
        )
        database["push_subscriptions"].insert_one(
            {
                "owner_user_id": user_id,
                "endpoint": "https://push.example.com/delete",
                "user_agent": "UnitTest Browser",
                "created_at": now - timedelta(days=1),
                "updated_at": now - timedelta(hours=1),
            }
        )

        regular_user_invite = client.post(
            "/api/admin/invites",
            json={"email": "operator@example.com"},
            headers=admin_headers(),
        ).json()
        client.post(
            "/api/auth/invites/accept",
            json={"token": regular_user_invite["token"], "password": "OperatorPass123"},
        )
        regular_user_token = client.post(
            "/api/auth/login",
            json={"email": "operator@example.com", "password": "OperatorPass123"},
        ).json()["access_token"]

        forbidden = client.post(
            f"/api/admin/users/{user_id}/actions/block",
            json={},
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        delete_user_response = client.post(
            f"/api/admin/users/{user_id}/actions/delete_user",
            json={},
            headers=admin_headers(),
        )

        remaining_user = database["users"].find_one({"_id": user_id})
        remaining_invites = list(database["invites"].find({"email": "delete-me@example.com"}))
        remaining_saved_searches = list(database["saved_searches"].find({"owner_user_id": user_id}))
        remaining_caches = list(database["saved_search_results_cache"].find({"owner_user_id": user_id}))
        remaining_tracked_lots = list(database["tracked_lots"].find({"owner_user_id": user_id}))
        remaining_snapshots = list(database["lot_snapshots"].find({"tracked_lot_id": str(tracked_lot_id)}))
        remaining_connections = list(database["provider_connections"].find({"owner_user_id": user_id}))
        remaining_push_subscriptions = list(database["push_subscriptions"].find({"owner_user_id": user_id}))

    assert forbidden.status_code == 403
    assert delete_user_response.status_code == 200
    counts = delete_user_response.json()["counts"]
    assert counts["users"] == 1
    assert counts["saved_searches"] == 1
    assert counts["tracked_lots"] == 1
    assert counts["lot_snapshots"] == 1
    assert counts["provider_connections"] == 1
    assert counts["push_subscriptions"] == 1
    assert counts["invites"] == 1
    assert remaining_user is None
    assert remaining_invites == []
    assert remaining_saved_searches == []
    assert remaining_caches == []
    assert remaining_tracked_lots == []
    assert remaining_snapshots == []
    assert remaining_connections == []
    assert remaining_push_subscriptions == []
