from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

def test_admin_overview_and_system_health_include_platform_metrics(client: TestClient, create_user, admin_headers) -> None:
    now = datetime.now(timezone.utc)

    with client:
        database = client.app.state.mongo.database
        active_user_id = create_user(
            email="active-user@example.com",
            created_at=now - timedelta(days=10),
            last_login_at=now - timedelta(hours=4),
        )
        blocked_user_id = create_user(
            email="blocked-user@example.com",
            status="blocked",
            created_at=now - timedelta(days=3),
        )

        database["invites"].insert_many(
            [
                {
                    "email": "pending@example.com",
                    "token": "pending-token",
                    "status": "pending",
                    "expires_at": now + timedelta(hours=2),
                    "accepted_at": None,
                    "revoked_at": None,
                    "created_at": now - timedelta(hours=1),
                    "created_by": "bootstrap-admin",
                },
                {
                    "email": "expired@example.com",
                    "token": "expired-token",
                    "status": "pending",
                    "expires_at": now - timedelta(hours=1),
                    "accepted_at": None,
                    "revoked_at": None,
                    "created_at": now - timedelta(days=1),
                    "created_by": "bootstrap-admin",
                },
                {
                    "email": "accepted@example.com",
                    "token": "accepted-token",
                    "status": "accepted",
                    "expires_at": now - timedelta(days=1),
                    "accepted_at": now - timedelta(hours=10),
                    "revoked_at": None,
                    "created_at": now - timedelta(days=2),
                    "created_by": "bootstrap-admin",
                },
            ]
        )
        database["provider_connections"].insert_many(
            [
                {
                    "owner_user_id": active_user_id,
                    "provider": "copart",
                    "status": "connected",
                    "account_label": "copart-user@example.com",
                    "created_at": now - timedelta(days=2),
                    "updated_at": now - timedelta(hours=2),
                    "connected_at": now - timedelta(days=2),
                    "bundle_version": 1,
                    "encrypted_session_bundle": "bundle",
                    "encrypted_session_bundle_key_version": "v1",
                    "bundle_captured_at": now - timedelta(days=2),
                    "bundle_expires_at": now + timedelta(days=1),
                },
                {
                    "owner_user_id": blocked_user_id,
                    "provider": "iaai",
                    "status": "reconnect_required",
                    "account_label": "iaai-user@example.com",
                    "created_at": now - timedelta(days=2),
                    "updated_at": now - timedelta(hours=3),
                    "connected_at": now - timedelta(days=2),
                    "bundle_version": 1,
                    "encrypted_session_bundle": None,
                    "encrypted_session_bundle_key_version": None,
                    "bundle_captured_at": None,
                    "bundle_expires_at": None,
                },
            ]
        )
        saved_search_id = database["saved_searches"].insert_one(
            {
                "owner_user_id": active_user_id,
                "label": "FORD F-150",
                "criteria": {"providers": ["copart"], "make": "FORD", "model": "F-150"},
                "result_count": 12,
                "created_at": now - timedelta(days=5),
                "updated_at": now - timedelta(days=5),
                "last_refresh_attempted_at": now - timedelta(hours=1),
                "last_refresh_succeeded_at": now - timedelta(days=1),
                "last_refresh_error": "Gateway unavailable",
                "last_refresh_retryable": True,
                "refresh_status": "retryable_failure",
                "last_refresh_outcome": "failed",
                "last_refresh_priority_class": "high",
            }
        ).inserted_id
        database["saved_search_results_cache"].insert_one(
            {
                "saved_search_id": saved_search_id,
                "owner_user_id": active_user_id,
                "result_count": 12,
                "new_lot_keys": ["copart:1", "copart:2"],
                "last_synced_at": now - timedelta(days=2),
                "created_at": now - timedelta(days=5),
                "updated_at": now - timedelta(days=2),
            }
        )
        tracked_lot_id = database["tracked_lots"].insert_one(
            {
                "owner_user_id": active_user_id,
                "provider": "copart",
                "provider_lot_id": "12345678",
                "lot_key": "copart:12345678",
                "auction_label": "Copart",
                "lot_number": "12345678",
                "title": "2020 TOYOTA CAMRY",
                "status": "live",
                "raw_status": "Live",
                "current_bid": 5200.0,
                "buy_now_price": None,
                "currency": "USD",
                "sale_date": now + timedelta(days=1),
                "last_checked_at": now - timedelta(days=2),
                "created_at": now - timedelta(days=4),
                "updated_at": now - timedelta(days=2),
                "has_unseen_update": True,
                "refresh_status": "retryable_failure",
                "last_refresh_error": "Timeout",
                "last_refresh_retryable": True,
                "last_refresh_attempted_at": now - timedelta(hours=2),
                "last_refresh_succeeded_at": now - timedelta(days=1),
            }
        ).inserted_id
        database["lot_snapshots"].insert_one(
            {
                "tracked_lot_id": str(tracked_lot_id),
                "provider": "copart",
                "provider_lot_id": "12345678",
                "lot_key": "copart:12345678",
                "lot_number": "12345678",
                "status": "live",
                "raw_status": "Live",
                "currency": "USD",
                "detected_at": now - timedelta(days=1),
            }
        )
        database["push_subscriptions"].insert_one(
            {
                "owner_user_id": active_user_id,
                "endpoint": "https://push.example.com/sub-1",
                "user_agent": "UnitTest Browser",
                "created_at": now - timedelta(days=1),
                "updated_at": now - timedelta(hours=2),
            }
        )
        database["system_status"].insert_one(
            {
                "_id": "live_sync",
                "availability": "degraded",
                "last_success_at": now - timedelta(hours=12),
                "last_success_source": "saved_search_poll",
                "last_failure_at": now + timedelta(minutes=1),
                "last_failure_source": "watchlist_refresh",
                "last_error_message": "Gateway timeout",
                "updated_at": now,
            }
        )

        overview_response = client.get("/api/admin/overview", headers=admin_headers())
        system_health_response = client.get("/api/admin/system-health", headers=admin_headers())

    assert overview_response.status_code == 200
    overview = overview_response.json()
    assert overview["users"]["total"] == 3
    assert overview["users"]["admins"] == 1
    assert overview["users"]["blocked"] == 1
    assert overview["invites"]["pending"] == 1
    assert overview["invites"]["expired"] == 1
    assert overview["providers"]["connected"] == 1
    assert overview["providers"]["reconnect_required"] == 1
    assert overview["searches"]["total_saved_searches"] == 1
    assert overview["searches"]["searches_with_new_matches"] == 1
    assert overview["watchlist"]["unseen_updates"] == 1
    assert overview["push"]["users_with_push"] == 1
    assert overview["system"]["live_sync_status"] == "degraded"

    assert system_health_response.status_code == 200
    system_health = system_health_response.json()
    assert system_health["environment"] == "test"
    assert system_health["blocked_users"] == 1
    assert system_health["expired_pending_invites"] == 1
    assert system_health["provider_reconnect_required"] == 1
    assert system_health["saved_search_attention"] == 1
    assert system_health["watchlist_attention"] == 1
    assert system_health["live_sync"]["status"] == "degraded"


def test_admin_overview_requires_admin_access(client: TestClient, admin_headers) -> None:
    with client:
        unauthorized = client.get("/api/admin/overview")
        regular_user_invite = client.post(
            "/api/admin/invites",
            json={"email": "member@example.com"},
            headers=admin_headers(),
        ).json()
        client.post(
            "/api/auth/invites/accept",
            json={"token": regular_user_invite["token"], "password": "MemberPass123"},
        )
        user_login = client.post(
            "/api/auth/login",
            json={"email": "member@example.com", "password": "MemberPass123"},
        )
        regular_user_headers = {"Authorization": f"Bearer {user_login.json()['access_token']}"}
        forbidden = client.get("/api/admin/system-health", headers=regular_user_headers)

    assert unauthorized.status_code == 401
    assert forbidden.status_code == 403
