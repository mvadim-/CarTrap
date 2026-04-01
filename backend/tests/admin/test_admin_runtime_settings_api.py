from __future__ import annotations

from datetime import datetime

from fastapi.testclient import TestClient


def test_admin_runtime_settings_are_admin_only_and_grouped(client: TestClient, create_user, admin_headers) -> None:
    with client:
        create_user(email="regular-user@example.com", password="UserPass123")
        regular_login = client.post(
            "/api/auth/login",
            json={"email": "regular-user@example.com", "password": "UserPass123"},
        )
        admin_response = client.get("/api/admin/runtime-settings", headers=admin_headers())
        regular_response = client.get(
            "/api/admin/runtime-settings",
            headers={"Authorization": f"Bearer {regular_login.json()['access_token']}"},
        )

    assert admin_response.status_code == 200
    groups = admin_response.json()["groups"]
    polling_group = next(group for group in groups if group["key"] == "polling")
    saved_search_item = next(item for item in polling_group["items"] if item["key"] == "saved_search_poll_interval_minutes")
    assert saved_search_item["effective_value"] == 15
    assert saved_search_item["default_value"] == 15
    assert saved_search_item["is_overridden"] is False
    assert regular_response.status_code == 403


def test_admin_runtime_settings_update_and_reset_drive_invite_ttl(client: TestClient, admin_headers) -> None:
    with client:
        update_response = client.post(
            "/api/admin/runtime-settings",
            json={
                "updates": [
                    {"key": "invite_ttl_hours", "value": 24},
                    {"key": "saved_search_poll_interval_minutes", "value": 6},
                ]
            },
            headers=admin_headers(),
        )
        invite_response = client.post(
            "/api/admin/invites",
            json={"email": "runtime-invite@example.com"},
            headers=admin_headers(),
        )
        reset_response = client.post(
            "/api/admin/runtime-settings/reset",
            json={"keys": ["invite_ttl_hours"]},
            headers=admin_headers(),
        )
        reset_invite_response = client.post(
            "/api/admin/invites",
            json={"email": "runtime-invite-reset@example.com"},
            headers=admin_headers(),
        )

    assert update_response.status_code == 200
    invite_payload = invite_response.json()
    invite_created_at = datetime.fromisoformat(invite_payload["created_at"].replace("Z", "+00:00"))
    invite_expires_at = datetime.fromisoformat(invite_payload["expires_at"].replace("Z", "+00:00"))
    assert int((invite_expires_at - invite_created_at).total_seconds()) == 24 * 60 * 60

    updated_groups = update_response.json()["groups"]
    invites_group = next(group for group in updated_groups if group["key"] == "invites")
    invite_ttl_item = next(item for item in invites_group["items"] if item["key"] == "invite_ttl_hours")
    assert invite_ttl_item["effective_value"] == 24
    assert invite_ttl_item["override_value"] == 24
    assert invite_ttl_item["updated_by"]

    assert reset_response.status_code == 200
    reset_invite_payload = reset_invite_response.json()
    reset_invite_created_at = datetime.fromisoformat(reset_invite_payload["created_at"].replace("Z", "+00:00"))
    reset_invite_expires_at = datetime.fromisoformat(reset_invite_payload["expires_at"].replace("Z", "+00:00"))
    assert int((reset_invite_expires_at - reset_invite_created_at).total_seconds()) == 72 * 60 * 60

    reset_groups = reset_response.json()["groups"]
    reset_invites_group = next(group for group in reset_groups if group["key"] == "invites")
    reset_item = next(item for item in reset_invites_group["items"] if item["key"] == "invite_ttl_hours")
    assert reset_item["override_value"] is None
    assert reset_item["effective_value"] == 72
    assert reset_item["is_overridden"] is False


def test_admin_runtime_settings_updates_are_partial_failure_safe(client: TestClient, admin_headers) -> None:
    with client:
        invalid_response = client.post(
            "/api/admin/runtime-settings",
            json={
                "updates": [
                    {"key": "saved_search_poll_interval_minutes", "value": 8},
                    {"key": "job_retry_backoff_seconds", "value": 0},
                ]
            },
            headers=admin_headers(),
        )
        list_response = client.get("/api/admin/runtime-settings", headers=admin_headers())

    assert invalid_response.status_code == 422
    groups = list_response.json()["groups"]
    polling_group = next(group for group in groups if group["key"] == "polling")
    saved_search_item = next(item for item in polling_group["items"] if item["key"] == "saved_search_poll_interval_minutes")
    assert saved_search_item["effective_value"] == 15
    assert saved_search_item["override_value"] is None
