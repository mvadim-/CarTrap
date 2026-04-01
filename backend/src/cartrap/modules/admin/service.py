"""Service layer for admin command-center aggregates and root actions."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
import secrets
from typing import Any

from fastapi import HTTPException, status
from pymongo.database import Database

from cartrap.config import Settings
from cartrap.modules.admin.schemas import (
    AdminActionResponse,
    AdminDangerZoneSummaryResponse,
    AdminOverviewResponse,
    AdminRecentActivityResponse,
    AdminSystemHealthResponse,
    AdminTrackedLotSummaryResponse,
    AdminUserDetailResponse,
    AdminUserDirectoryResponse,
)
from cartrap.modules.auction_domain.models import PROVIDER_COPART, build_lot_key
from cartrap.modules.auth.models import (
    INVITE_ACCEPTED,
    INVITE_PENDING,
    INVITE_REVOKED,
    ROLE_ADMIN,
    ROLE_USER,
    USER_STATUS_ACTIVE,
    USER_STATUS_BLOCKED,
)
from cartrap.modules.auth.repository import AuthRepository
from cartrap.modules.auth.service import AuthService
from cartrap.modules.monitoring.polling_policy import get_poll_interval_minutes
from cartrap.modules.notifications.repository import NotificationRepository
from cartrap.modules.notifications.service import NotificationService
from cartrap.modules.provider_connections.models import (
    PROVIDER_DISPLAY_NAMES,
    STATUS_CONNECTED,
    STATUS_DISCONNECTED,
    STATUS_ERROR,
    STATUS_EXPIRING,
    STATUS_RECONNECT_REQUIRED,
    USABLE_CONNECTION_STATUSES,
)
from cartrap.modules.provider_connections.repository import ProviderConnectionRepository
from cartrap.modules.search.repository import SavedSearchRepository
from cartrap.modules.runtime_settings.service import RuntimeSettingsService
from cartrap.modules.system_status.service import SystemStatusService, build_freshness_envelope
from cartrap.modules.watchlist.repository import WatchlistRepository


DIRECTORY_SORT_OPTIONS: dict[str, tuple[str, bool]] = {
    "created_at_desc": ("created_at", True),
    "created_at_asc": ("created_at", False),
    "last_login_desc": ("last_login_at", True),
    "last_login_asc": ("last_login_at", False),
    "email_asc": ("email", False),
    "email_desc": ("email", True),
}


class AdminService:
    def __init__(
        self,
        database: Database,
        settings: Settings,
        *,
        runtime_settings_service: RuntimeSettingsService | None = None,
    ) -> None:
        self._settings = settings
        self._runtime_settings_service = runtime_settings_service
        self._auth_repository = AuthRepository(database)
        self._saved_search_repository = SavedSearchRepository(database)
        self._watchlist_repository = WatchlistRepository(database)
        self._provider_connection_repository = ProviderConnectionRepository(database)
        self._notification_repository = NotificationRepository(database)
        self._system_status_service = SystemStatusService(
            database,
            live_sync_stale_after_minutes=self._get_runtime_value(
                "live_sync_stale_after_minutes",
                fallback=self._settings.live_sync_stale_after_minutes,
            ),
        )

    def list_invites(self) -> dict:
        return {
            "items": [AuthService.serialize_invite(invite) for invite in self._auth_repository.list_invites()]
        }

    def get_runtime_settings(self) -> dict:
        runtime_settings_service = self._require_runtime_settings_service()
        return {"groups": runtime_settings_service.list_settings_grouped()}

    def update_runtime_settings(self, updates: list[dict], *, updated_by: str) -> dict:
        runtime_settings_service = self._require_runtime_settings_service()
        normalized_updates = {item["key"]: item["value"] for item in updates}
        runtime_settings_service.update_settings(normalized_updates, updated_by=updated_by)
        return self.get_runtime_settings()

    def reset_runtime_settings(self, keys: list[str]) -> dict:
        runtime_settings_service = self._require_runtime_settings_service()
        runtime_settings_service.reset_settings(keys)
        return self.get_runtime_settings()

    def get_overview(self) -> dict:
        users = self._auth_repository.list_users()
        invites = self._auth_repository.list_invites()
        related = self._load_related_data()
        live_sync = self._system_status_service.get_live_sync_status()
        now = self._now()

        users_with_push = len(related["subscriptions_by_owner"])
        provider_states = {
            owner_user_id: self._summarize_provider_state(connections)
            for owner_user_id, connections in related["connections_by_owner"].items()
        }
        pending_invites = [invite for invite in invites if invite.get("status") == INVITE_PENDING]
        expired_invites = [invite for invite in pending_invites if self._is_invite_expired(invite, now)]

        searches_with_new_matches = 0
        for cache in related["saved_search_caches"]:
            if self._get_cache_new_count(cache) > 0:
                searches_with_new_matches += 1

        saved_search_attention = sum(
            1 for saved_search in related["saved_searches"] if self._saved_search_needs_attention(saved_search, related["cache_by_search_id"].get(saved_search["_id"]), live_sync)
        )
        watchlist_attention = sum(
            1 for tracked_lot in related["tracked_lots"] if self._tracked_lot_needs_attention(tracked_lot, live_sync)
        )

        return AdminOverviewResponse(
            generated_at=now,
            users={
                "total": len(users),
                "admins": sum(1 for user in users if user.get("role") == ROLE_ADMIN),
                "regular_users": sum(1 for user in users if user.get("role") == ROLE_USER),
                "active_last_24h": sum(1 for user in users if self._logged_in_within(user, timedelta(hours=24), now)),
                "active_last_7d": sum(1 for user in users if self._logged_in_within(user, timedelta(days=7), now)),
                "blocked": sum(1 for user in users if user.get("status") == USER_STATUS_BLOCKED),
                "disabled": sum(1 for user in users if user.get("status") not in {USER_STATUS_ACTIVE, USER_STATUS_BLOCKED}),
            },
            invites={
                "pending": len(pending_invites) - len(expired_invites),
                "accepted": sum(1 for invite in invites if invite.get("status") == INVITE_ACCEPTED),
                "revoked": sum(1 for invite in invites if invite.get("status") == INVITE_REVOKED),
                "expired": len(expired_invites),
            },
            providers={
                "total_connections": len(related["connections"]),
                "connected": sum(1 for connection in related["connections"] if connection.get("status") == STATUS_CONNECTED),
                "expiring": sum(1 for connection in related["connections"] if connection.get("status") == STATUS_EXPIRING),
                "reconnect_required": sum(
                    1 for connection in related["connections"] if connection.get("status") == STATUS_RECONNECT_REQUIRED
                ),
                "disconnected": sum(1 for connection in related["connections"] if connection.get("status") == STATUS_DISCONNECTED),
                "error": sum(1 for connection in related["connections"] if connection.get("status") == STATUS_ERROR),
                "connected_users": sum(1 for state in provider_states.values() if state == "connected"),
                "reconnect_required_users": sum(1 for state in provider_states.values() if state == "reconnect_required"),
                "disconnected_users": sum(1 for state in provider_states.values() if state == "disconnected"),
            },
            searches={
                "total_saved_searches": len(related["saved_searches"]),
                "users_with_saved_searches": len(related["saved_searches_by_owner"]),
                "stale_or_problem": saved_search_attention,
                "searches_with_new_matches": searches_with_new_matches,
            },
            watchlist={
                "total_tracked_lots": len(related["tracked_lots"]),
                "users_with_tracked_lots": len(related["tracked_lots_by_owner"]),
                "unseen_updates": sum(1 for tracked_lot in related["tracked_lots"] if tracked_lot.get("has_unseen_update")),
                "stale_or_problem": watchlist_attention,
            },
            push={
                "total_subscriptions": len(related["subscriptions"]),
                "users_with_push": users_with_push,
                "users_without_push": max(len(users) - users_with_push, 0),
            },
            system={
                "live_sync_status": live_sync.get("status", "available"),
                "stale": bool(live_sync.get("stale", False)),
                "last_success_at": live_sync.get("last_success_at"),
                "last_failure_at": live_sync.get("last_failure_at"),
                "last_error_message": live_sync.get("last_error_message"),
            },
        ).model_dump(mode="json")

    def get_system_health(self) -> dict:
        users = self._auth_repository.list_users()
        invites = self._auth_repository.list_invites()
        related = self._load_related_data()
        live_sync = self._system_status_service.get_live_sync_status()
        now = self._now()

        return AdminSystemHealthResponse(
            generated_at=now,
            app_name=self._settings.app_name,
            environment=self._settings.environment,
            live_sync=live_sync,
            blocked_users=sum(1 for user in users if user.get("status") == USER_STATUS_BLOCKED),
            expired_pending_invites=sum(1 for invite in invites if self._is_invite_expired(invite, now)),
            provider_reconnect_required=sum(
                1 for connection in related["connections"] if connection.get("status") == STATUS_RECONNECT_REQUIRED
            ),
            saved_search_attention=sum(
                1
                for saved_search in related["saved_searches"]
                if self._saved_search_needs_attention(saved_search, related["cache_by_search_id"].get(saved_search["_id"]), live_sync)
            ),
            watchlist_attention=sum(
                1 for tracked_lot in related["tracked_lots"] if self._tracked_lot_needs_attention(tracked_lot, live_sync)
            ),
        ).model_dump(mode="json")

    def list_users(
        self,
        *,
        query: str | None,
        role: str | None,
        status_filter: str | None,
        provider_state: str | None,
        push_state: str | None,
        saved_search_state: str | None,
        watchlist_state: str | None,
        last_login: str | None,
        sort: str,
        page: int,
        page_size: int,
    ) -> dict:
        users = self._auth_repository.list_users()
        related = self._load_related_data()
        rows = [self._build_directory_row(user, related) for user in users]
        filtered = [
            row
            for row in rows
            if self._matches_directory_filters(
                row,
                query=query,
                role=role,
                status_filter=status_filter,
                provider_state=provider_state,
                push_state=push_state,
                saved_search_state=saved_search_state,
                watchlist_state=watchlist_state,
                last_login=last_login,
            )
        ]
        sorted_rows = self._sort_directory_rows(filtered, sort)
        start = max(page - 1, 0) * page_size
        end = start + page_size
        return AdminUserDirectoryResponse(
            items=sorted_rows[start:end],
            total=len(filtered),
            page=page,
            page_size=page_size,
        ).model_dump(mode="json")

    def get_user_detail(self, user_id: str) -> dict:
        user = self._require_user(user_id)
        live_sync = self._system_status_service.get_live_sync_status()
        invites = self._auth_repository.list_invites({"email": user["email"]})
        provider_connections = self._provider_connection_repository.list_for_owner(user_id)
        saved_searches = self._saved_search_repository.list_saved_searches_for_owner(user_id)
        saved_search_caches = self._saved_search_repository.list_saved_search_caches_for_owner(
            user_id, [str(document["_id"]) for document in saved_searches]
        )
        cache_by_search_id = {cache["saved_search_id"]: cache for cache in saved_search_caches}
        tracked_lots = self._watchlist_repository.list_tracked_lots_for_owner(user_id)
        push_subscriptions = self._notification_repository.list_subscriptions_for_owner(user_id)

        return AdminUserDetailResponse(
            account=AuthService.serialize_user_for_admin(user),
            counts={
                "provider_connections": len(provider_connections),
                "saved_searches": len(saved_searches),
                "tracked_lots": len(tracked_lots),
                "push_subscriptions": len(push_subscriptions),
            },
            invites=[AuthService.serialize_invite(invite) for invite in invites],
            provider_connections=[self._serialize_provider_connection(connection) for connection in provider_connections],
            saved_searches=[
                self._serialize_saved_search(saved_search, cache_by_search_id.get(saved_search["_id"]), live_sync)
                for saved_search in saved_searches
            ],
            tracked_lots=[self._serialize_tracked_lot(tracked_lot, live_sync) for tracked_lot in tracked_lots],
            push_subscriptions=[NotificationService.serialize_subscription(item) for item in push_subscriptions],
            recent_activity=AdminRecentActivityResponse(
                last_login_at=user.get("last_login_at"),
                last_saved_search_at=self._max_datetime(saved_searches, "created_at"),
                last_tracked_lot_at=self._max_datetime(tracked_lots, "created_at"),
                last_push_subscription_at=self._max_datetime(push_subscriptions, "updated_at"),
                last_provider_activity_at=self._max_datetime(provider_connections, "updated_at"),
                has_unseen_watchlist_updates=any(item.get("has_unseen_update") for item in tracked_lots),
            ),
            danger_zone=AdminDangerZoneSummaryResponse(
                provider_connections=len(provider_connections),
                saved_searches=len(saved_searches),
                tracked_lots=len(tracked_lots),
                push_subscriptions=len(push_subscriptions),
                lot_snapshots=sum(
                    self._watchlist_repository.count_snapshots_for_tracked_lot(str(tracked_lot["_id"]))
                    for tracked_lot in tracked_lots
                ),
                invites=len(invites),
            ),
        ).model_dump(mode="json")

    def execute_user_action(self, user_id: str, action: str, payload: dict | None = None) -> dict:
        target_user = self._require_user(user_id)
        action_payload = payload or {}
        normalized_action = action.strip().lower()

        if normalized_action == "block":
            self._ensure_not_last_active_admin(target_user, "block")
            updated = self._update_user(target_user, {"status": USER_STATUS_BLOCKED})
            return self._action_response(
                action="block",
                scope="account",
                message=f"Blocked {target_user['email']}.",
                user=updated,
            )

        if normalized_action == "unblock":
            updated = self._update_user(target_user, {"status": USER_STATUS_ACTIVE})
            return self._action_response(
                action="unblock",
                scope="account",
                message=f"Restored access for {target_user['email']}.",
                user=updated,
            )

        if normalized_action == "promote":
            updated = self._update_user(target_user, {"role": ROLE_ADMIN})
            return self._action_response(
                action="promote",
                scope="account",
                message=f"Promoted {target_user['email']} to admin.",
                user=updated,
            )

        if normalized_action == "demote":
            self._ensure_not_last_active_admin(target_user, "demote")
            updated = self._update_user(target_user, {"role": ROLE_USER})
            return self._action_response(
                action="demote",
                scope="account",
                message=f"Demoted {target_user['email']} to user.",
                user=updated,
            )

        if normalized_action == "reset_password":
            temporary_password = self._generate_temporary_password()
            updated = self._update_user(
                target_user,
                {"password_hash": AuthService.hash_password(temporary_password), "last_login_at": None},
            )
            return self._action_response(
                action="reset_password",
                scope="account",
                message=f"Issued a temporary password for {target_user['email']}.",
                user=updated,
                generated_password=temporary_password,
            )

        if normalized_action == "disconnect_provider":
            provider = self._normalize_provider(action_payload.get("provider"))
            connection = self._provider_connection_repository.find_by_user_and_provider(user_id, provider)
            if connection is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider connection not found.")
            self._disconnect_connection(connection)
            return self._action_response(
                action="disconnect_provider",
                scope="provider",
                message=f"Disconnected {self._provider_label(provider)} for {target_user['email']}.",
                counts={"provider_connections": 1},
            )

        if normalized_action == "disconnect_all_providers":
            disconnected_count = 0
            for connection in self._provider_connection_repository.list_for_owner(user_id):
                self._disconnect_connection(connection)
                disconnected_count += 1
            return self._action_response(
                action="disconnect_all_providers",
                scope="provider",
                message=f"Disconnected {disconnected_count} provider connection(s) for {target_user['email']}.",
                counts={"provider_connections": disconnected_count},
            )

        if normalized_action == "delete_saved_search":
            resource_id = action_payload.get("resource_id")
            saved_search = self._saved_search_repository.find_saved_search_by_id_for_owner(str(resource_id), user_id)
            if saved_search is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Saved search not found.")
            self._saved_search_repository.delete_saved_search(str(saved_search["_id"]))
            return self._action_response(
                action="delete_saved_search",
                scope="resource",
                message=f"Deleted saved search for {target_user['email']}.",
                counts={"saved_searches": 1, "saved_search_caches": 1},
            )

        if normalized_action == "delete_all_saved_searches":
            counts = self._saved_search_repository.delete_saved_searches_for_owner(user_id)
            return self._action_response(
                action="delete_all_saved_searches",
                scope="resource",
                message=f"Deleted saved searches for {target_user['email']}.",
                counts=counts,
            )

        if normalized_action == "delete_tracked_lot":
            resource_id = action_payload.get("resource_id")
            tracked_lot = self._watchlist_repository.find_tracked_lot_by_id_for_owner(str(resource_id), user_id)
            if tracked_lot is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tracked lot not found.")
            snapshot_count = self._watchlist_repository.count_snapshots_for_tracked_lot(str(tracked_lot["_id"]))
            self._watchlist_repository.delete_tracked_lot(str(tracked_lot["_id"]))
            return self._action_response(
                action="delete_tracked_lot",
                scope="resource",
                message=f"Deleted tracked lot for {target_user['email']}.",
                counts={"tracked_lots": 1, "lot_snapshots": snapshot_count},
            )

        if normalized_action == "delete_all_tracked_lots":
            counts = self._watchlist_repository.delete_tracked_lots_for_owner(user_id)
            return self._action_response(
                action="delete_all_tracked_lots",
                scope="resource",
                message=f"Deleted tracked lots for {target_user['email']}.",
                counts=counts,
            )

        if normalized_action == "delete_push_subscription":
            resource_id = str(action_payload.get("resource_id") or "")
            subscription = next(
                (
                    item
                    for item in self._notification_repository.list_subscriptions_for_owner(user_id)
                    if str(item["_id"]) == resource_id
                ),
                None,
            )
            if subscription is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Push subscription not found.")
            self._notification_repository.delete_subscription_by_id(resource_id)
            return self._action_response(
                action="delete_push_subscription",
                scope="resource",
                message=f"Deleted push subscription for {target_user['email']}.",
                counts={"push_subscriptions": 1},
            )

        if normalized_action == "delete_all_push_subscriptions":
            deleted_count = self._notification_repository.delete_subscriptions_for_owner(user_id)
            return self._action_response(
                action="delete_all_push_subscriptions",
                scope="resource",
                message=f"Deleted push subscriptions for {target_user['email']}.",
                counts={"push_subscriptions": deleted_count},
            )

        if normalized_action == "purge_snapshots":
            resource_id = action_payload.get("resource_id")
            if resource_id:
                tracked_lot = self._watchlist_repository.find_tracked_lot_by_id_for_owner(str(resource_id), user_id)
                if tracked_lot is None:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tracked lot not found.")
                deleted_count = self._watchlist_repository.purge_snapshots_for_tracked_lot(str(tracked_lot["_id"]))
            else:
                deleted_count = self._watchlist_repository.purge_snapshots_for_owner(user_id)
            return self._action_response(
                action="purge_snapshots",
                scope="resource",
                message=f"Purged snapshots for {target_user['email']}.",
                counts={"lot_snapshots": deleted_count},
            )

        if normalized_action == "delete_user":
            self._ensure_not_last_active_admin(target_user, "delete")
            counts = {}
            counts.update(self._saved_search_repository.delete_saved_searches_for_owner(user_id))
            tracked_counts = self._watchlist_repository.delete_tracked_lots_for_owner(user_id)
            counts["provider_connections"] = self._provider_connection_repository.delete_for_owner(user_id)
            counts["push_subscriptions"] = self._notification_repository.delete_subscriptions_for_owner(user_id)
            counts["invites"] = self._auth_repository.delete_invites_by_email(target_user["email"])
            counts["tracked_lots"] = tracked_counts["tracked_lots"]
            counts["lot_snapshots"] = tracked_counts["lot_snapshots"]
            counts["users"] = self._auth_repository.delete_user(user_id)
            return self._action_response(
                action="delete_user",
                scope="danger",
                message=f"Deleted {target_user['email']} and related data.",
                counts=counts,
            )

        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unsupported admin action: {action}")

    def _require_user(self, user_id: str) -> dict:
        user = self._auth_repository.find_user_by_id(user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
        return user

    def _update_user(self, user: dict, payload: dict[str, Any]) -> dict:
        updated = self._auth_repository.update_user(
            str(user["_id"]),
            {
                **payload,
                "updated_at": self._now(),
            },
        )
        if updated is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
        return AuthService.serialize_user_for_admin(updated)

    def _disconnect_connection(self, connection: dict) -> None:
        now = self._now()
        self._provider_connection_repository.disconnect_connection(
            str(connection["_id"]),
            disconnected_at=now,
            updated_at=now,
        )

    def _ensure_not_last_active_admin(self, user: dict, operation: str) -> None:
        if user.get("role") != ROLE_ADMIN or user.get("status") != USER_STATUS_ACTIVE:
            return
        other_active_admins = self._auth_repository.count_other_users_with_role_and_status(
            role=ROLE_ADMIN,
            status=USER_STATUS_ACTIVE,
            exclude_user_id=str(user["_id"]),
        )
        if other_active_admins == 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot {operation} the last active admin account.",
            )

    def _load_related_data(self) -> dict[str, Any]:
        saved_searches = self._saved_search_repository.list_all_saved_searches()
        tracked_lots = self._watchlist_repository.list_all_tracked_lots()
        connections = self._provider_connection_repository.list_all()
        subscriptions = self._notification_repository.list_all_subscriptions()
        saved_search_caches = self._saved_search_repository.list_all_saved_search_caches()

        saved_searches_by_owner = self._group_by_owner(saved_searches)
        tracked_lots_by_owner = self._group_by_owner(tracked_lots)
        connections_by_owner = self._group_by_owner(connections)
        subscriptions_by_owner = self._group_by_owner(subscriptions)
        cache_by_search_id = {cache["saved_search_id"]: cache for cache in saved_search_caches}

        return {
            "saved_searches": saved_searches,
            "saved_searches_by_owner": saved_searches_by_owner,
            "tracked_lots": tracked_lots,
            "tracked_lots_by_owner": tracked_lots_by_owner,
            "connections": connections,
            "connections_by_owner": connections_by_owner,
            "subscriptions": subscriptions,
            "subscriptions_by_owner": subscriptions_by_owner,
            "saved_search_caches": saved_search_caches,
            "cache_by_search_id": cache_by_search_id,
            "pending_invites_by_email": self._pending_invites_by_email(),
        }

    def _pending_invites_by_email(self) -> dict[str, list[dict]]:
        invites_by_email: dict[str, list[dict]] = defaultdict(list)
        for invite in self._auth_repository.list_invites():
            if invite.get("status") == INVITE_PENDING:
                invites_by_email[str(invite.get("email", "")).lower()].append(invite)
        return invites_by_email

    def _build_directory_row(self, user: dict, related: dict[str, Any]) -> dict:
        user_id = str(user["_id"])
        email = str(user["email"]).lower()
        connections = related["connections_by_owner"].get(user_id, [])
        tracked_lots = related["tracked_lots_by_owner"].get(user_id, [])
        return {
            "id": user_id,
            "email": email,
            "role": user["role"],
            "status": user["status"],
            "created_at": user["created_at"],
            "updated_at": user["updated_at"],
            "last_login_at": user.get("last_login_at"),
            "provider_state": self._summarize_provider_state(connections),
            "counts": {
                "provider_connections": len(connections),
                "saved_searches": len(related["saved_searches_by_owner"].get(user_id, [])),
                "tracked_lots": len(tracked_lots),
                "push_subscriptions": len(related["subscriptions_by_owner"].get(user_id, [])),
            },
            "flags": {
                "has_pending_invite": email in related["pending_invites_by_email"],
                "has_reconnect_required_provider": any(
                    connection.get("status") == STATUS_RECONNECT_REQUIRED for connection in connections
                ),
                "has_unseen_watchlist_updates": any(item.get("has_unseen_update") for item in tracked_lots),
            },
        }

    def _matches_directory_filters(
        self,
        row: dict,
        *,
        query: str | None,
        role: str | None,
        status_filter: str | None,
        provider_state: str | None,
        push_state: str | None,
        saved_search_state: str | None,
        watchlist_state: str | None,
        last_login: str | None,
    ) -> bool:
        normalized_query = (query or "").strip().lower()
        if normalized_query and normalized_query not in row["email"]:
            return False
        if role and role != "any" and row["role"] != role:
            return False
        if status_filter and status_filter != "any" and row["status"] != status_filter:
            return False
        if provider_state and provider_state != "any" and row["provider_state"] != provider_state:
            return False
        if push_state == "has_push" and row["counts"]["push_subscriptions"] <= 0:
            return False
        if push_state == "no_push" and row["counts"]["push_subscriptions"] > 0:
            return False
        if saved_search_state == "has_saved_searches" and row["counts"]["saved_searches"] <= 0:
            return False
        if saved_search_state == "no_saved_searches" and row["counts"]["saved_searches"] > 0:
            return False
        if watchlist_state == "has_tracked_lots" and row["counts"]["tracked_lots"] <= 0:
            return False
        if watchlist_state == "no_tracked_lots" and row["counts"]["tracked_lots"] > 0:
            return False
        if watchlist_state == "unseen_updates" and not row["flags"]["has_unseen_watchlist_updates"]:
            return False
        if last_login and last_login != "any" and not self._matches_last_login_filter(row.get("last_login_at"), last_login):
            return False
        return True

    def _matches_last_login_filter(self, last_login_at: datetime | None, filter_value: str) -> bool:
        now = self._now()
        if filter_value == "never":
            return last_login_at is None
        if last_login_at is None:
            return False
        age = now - last_login_at
        if filter_value == "24h":
            return age <= timedelta(hours=24)
        if filter_value == "7d":
            return age <= timedelta(days=7)
        if filter_value == "stale":
            return age > timedelta(days=7)
        return True

    def _sort_directory_rows(self, rows: list[dict], sort_key: str) -> list[dict]:
        attribute, reverse = DIRECTORY_SORT_OPTIONS.get(sort_key, DIRECTORY_SORT_OPTIONS["created_at_desc"])

        def build_sort_value(row: dict) -> tuple:
            value = row.get(attribute)
            if attribute == "email":
                return (str(value or "").lower(),)
            if value is None:
                return (datetime.min.replace(tzinfo=timezone.utc),)
            return (value,)

        return sorted(rows, key=build_sort_value, reverse=reverse)

    def _serialize_provider_connection(self, document: dict) -> dict:
        status_value = document.get("status") or STATUS_ERROR
        provider = document["provider"]
        return {
            "id": str(document["_id"]),
            "provider": provider,
            "provider_label": self._provider_label(provider),
            "status": status_value,
            "account_label": document.get("account_label"),
            "connected_at": document.get("connected_at"),
            "disconnected_at": document.get("disconnected_at"),
            "last_verified_at": document.get("last_verified_at"),
            "last_used_at": document.get("last_used_at"),
            "expires_at": document.get("bundle_expires_at"),
            "reconnect_required": status_value == STATUS_RECONNECT_REQUIRED,
            "usable": status_value in USABLE_CONNECTION_STATUSES,
            "bundle_version": int(document.get("bundle_version") or 1),
            "bundle": (
                {
                    "key_version": document["encrypted_session_bundle_key_version"],
                    "captured_at": document.get("bundle_captured_at"),
                    "expires_at": document.get("bundle_expires_at"),
                }
                if document.get("encrypted_session_bundle")
                else None
            ),
            "last_error": document.get("last_error"),
            "created_at": document["created_at"],
            "updated_at": document["updated_at"],
        }

    def _serialize_saved_search(self, document: dict, cache_document: dict | None, live_sync_status: dict | None) -> dict:
        cache_new_count = self._get_cache_new_count(cache_document)
        last_synced_at = cache_document.get("last_synced_at") if cache_document else None
        saved_search_poll_interval_minutes = self._get_runtime_value(
            "saved_search_poll_interval_minutes",
            fallback=self._settings.saved_search_poll_interval_minutes,
        )
        return {
            "id": str(document["_id"]),
            "label": document["label"],
            "providers": list(document.get("criteria", {}).get("providers", [PROVIDER_COPART])),
            "result_count": document.get("result_count"),
            "cached_result_count": cache_document.get("result_count") if cache_document else None,
            "new_count": cache_new_count,
            "last_synced_at": last_synced_at,
            "freshness": build_freshness_envelope(
                last_synced_at=last_synced_at,
                stale_after_window=timedelta(minutes=saved_search_poll_interval_minutes),
                live_sync_status=live_sync_status,
            ),
            "refresh_state": self._serialize_saved_search_refresh_state(document),
            "created_at": document["created_at"],
        }

    def _serialize_tracked_lot(self, document: dict, live_sync_status: dict | None) -> dict:
        current_time = self._now()
        watchlist_default_poll_interval_minutes = self._get_runtime_value(
            "watchlist_default_poll_interval_minutes",
            fallback=self._settings.watchlist_default_poll_interval_minutes,
        )
        return AdminTrackedLotSummaryResponse(
            id=str(document["_id"]),
            provider=document.get("provider") or PROVIDER_COPART,
            lot_key=document.get("lot_key")
            or build_lot_key(document.get("provider") or PROVIDER_COPART, document.get("provider_lot_id"), document["lot_number"]),
            lot_number=document["lot_number"],
            title=document["title"],
            status=document["status"],
            raw_status=document["raw_status"],
            current_bid=document.get("current_bid"),
            buy_now_price=document.get("buy_now_price"),
            currency=document["currency"],
            sale_date=document.get("sale_date"),
            last_checked_at=document.get("last_checked_at"),
            freshness=build_freshness_envelope(
                last_synced_at=document.get("last_checked_at"),
                stale_after_window=timedelta(
                    minutes=get_poll_interval_minutes(
                        document,
                        current_time,
                        default_interval_minutes=self._settings.watchlist_default_poll_interval_minutes,
                    )
                ),
                live_sync_status=live_sync_status,
                current_time=current_time,
            ),
            refresh_state=self._serialize_tracked_lot_refresh_state(document),
            has_unseen_update=bool(document.get("has_unseen_update", False)),
            latest_change_at=document.get("latest_change_at"),
            created_at=document["created_at"],
        ).model_dump(mode="json")

    @staticmethod
    def _serialize_saved_search_refresh_state(document: dict) -> dict:
        return {
            "status": document.get("refresh_status") or "idle",
            "last_attempted_at": document.get("last_refresh_attempted_at"),
            "last_succeeded_at": document.get("last_refresh_succeeded_at"),
            "next_retry_at": document.get("next_refresh_retry_at"),
            "error_message": document.get("last_refresh_error"),
            "retryable": bool(document.get("last_refresh_retryable", False)),
            "priority_class": document.get("last_refresh_priority_class"),
            "last_outcome": document.get("last_refresh_outcome"),
            "metrics": {
                "new_matches": int(document.get("last_refresh_new_matches") or 0),
                "cached_new_count": int(document.get("last_refresh_cached_new_count") or 0),
            },
        }

    @staticmethod
    def _serialize_tracked_lot_refresh_state(document: dict) -> dict:
        tracked_lot_status = document.get("refresh_status") or "idle"
        if tracked_lot_status == "idle" and document.get("repair_requested_at") is not None:
            tracked_lot_status = "repair_pending"
        return {
            "status": tracked_lot_status,
            "last_attempted_at": document.get("last_refresh_attempted_at"),
            "last_succeeded_at": document.get("last_refresh_succeeded_at"),
            "next_retry_at": document.get("next_refresh_retry_at"),
            "error_message": document.get("last_refresh_error"),
            "retryable": bool(document.get("last_refresh_retryable", False)),
            "priority_class": document.get("last_refresh_priority_class"),
            "last_outcome": document.get("last_refresh_outcome"),
            "metrics": {
                "change_count": int(document.get("last_refresh_change_count") or 0),
                "reminder_count": int(document.get("last_refresh_reminder_count") or 0),
            },
        }

    def _saved_search_needs_attention(self, document: dict, cache_document: dict | None, live_sync_status: dict | None) -> bool:
        saved_search_poll_interval_minutes = self._get_runtime_value(
            "saved_search_poll_interval_minutes",
            fallback=self._settings.saved_search_poll_interval_minutes,
        )
        freshness = build_freshness_envelope(
            last_synced_at=cache_document.get("last_synced_at") if cache_document else None,
            stale_after_window=timedelta(minutes=saved_search_poll_interval_minutes),
            live_sync_status=live_sync_status,
        )
        return freshness["status"] in {"degraded", "outdated", "unknown"} or (document.get("refresh_status") or "idle") != "idle"

    def _tracked_lot_needs_attention(self, document: dict, live_sync_status: dict | None) -> bool:
        current_time = self._now()
        watchlist_default_poll_interval_minutes = self._get_runtime_value(
            "watchlist_default_poll_interval_minutes",
            fallback=self._settings.watchlist_default_poll_interval_minutes,
        )
        freshness = build_freshness_envelope(
            last_synced_at=document.get("last_checked_at"),
            stale_after_window=timedelta(
                minutes=get_poll_interval_minutes(
                    document,
                    current_time,
                    default_interval_minutes=watchlist_default_poll_interval_minutes,
                )
            ),
            live_sync_status=live_sync_status,
            current_time=current_time,
        )
        refresh_status = document.get("refresh_status") or "idle"
        if refresh_status == "idle" and document.get("repair_requested_at") is not None:
            refresh_status = "repair_pending"
        return freshness["status"] in {"degraded", "outdated", "unknown"} or refresh_status != "idle"

    @staticmethod
    def _get_cache_new_count(cache_document: dict | None) -> int:
        if cache_document is None:
            return 0
        new_lot_keys = cache_document.get("new_lot_keys")
        if isinstance(new_lot_keys, list):
            return len(new_lot_keys)
        legacy_numbers = cache_document.get("new_lot_numbers")
        if isinstance(legacy_numbers, list):
            return len(legacy_numbers)
        return 0

    @staticmethod
    def _summarize_provider_state(connections: list[dict]) -> str:
        if not connections:
            return "none"
        statuses = {connection.get("status") for connection in connections}
        if STATUS_RECONNECT_REQUIRED in statuses:
            return "reconnect_required"
        if STATUS_CONNECTED in statuses or STATUS_EXPIRING in statuses:
            return "connected"
        if STATUS_ERROR in statuses:
            return "error"
        if STATUS_DISCONNECTED in statuses:
            return "disconnected"
        return "unknown"

    @staticmethod
    def _group_by_owner(documents: list[dict]) -> dict[str, list[dict]]:
        grouped: dict[str, list[dict]] = defaultdict(list)
        for document in documents:
            owner_user_id = document.get("owner_user_id")
            if owner_user_id:
                grouped[str(owner_user_id)].append(document)
        return grouped

    @staticmethod
    def _max_datetime(documents: list[dict], field_name: str) -> datetime | None:
        values = [document.get(field_name) for document in documents if document.get(field_name) is not None]
        if not values:
            return None
        return max(values)

    @staticmethod
    def _provider_label(provider: str) -> str:
        return PROVIDER_DISPLAY_NAMES.get(provider, provider.upper())

    @staticmethod
    def _is_invite_expired(invite: dict, now: datetime) -> bool:
        return invite.get("status") == INVITE_PENDING and invite.get("expires_at") is not None and invite["expires_at"] < now

    @staticmethod
    def _logged_in_within(user: dict, window: timedelta, now: datetime) -> bool:
        last_login_at = user.get("last_login_at")
        return last_login_at is not None and now - last_login_at <= window

    def _normalize_provider(self, provider: str | None) -> str:
        normalized = str(provider or "").strip().lower()
        if normalized not in PROVIDER_DISPLAY_NAMES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported provider.")
        return normalized

    @staticmethod
    def _generate_temporary_password() -> str:
        return f"Temp-{secrets.token_urlsafe(10)}1a"

    @staticmethod
    def _action_response(
        *,
        action: str,
        scope: str,
        message: str,
        user: dict | None = None,
        generated_password: str | None = None,
        counts: dict[str, int] | None = None,
    ) -> dict:
        return AdminActionResponse(
            action=action,
            scope=scope,
            message=message,
            user=user,
            generated_password=generated_password,
            counts=counts or {},
        ).model_dump(mode="json")

    def _get_runtime_value(self, key: str, *, fallback: int) -> int:
        if self._runtime_settings_service is None:
            return fallback
        return int(self._runtime_settings_service.get_effective_value(key))

    def _require_runtime_settings_service(self) -> RuntimeSettingsService:
        if self._runtime_settings_service is None:
            raise RuntimeError("Runtime settings service is not configured.")
        return self._runtime_settings_service

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)
