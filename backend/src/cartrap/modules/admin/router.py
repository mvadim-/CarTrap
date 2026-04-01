"""Admin-only endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, Request

from cartrap.api.dependencies import get_auth_service, require_admin
from cartrap.modules.auth.schemas import InviteCreateRequest, InviteResponse
from cartrap.modules.auth.service import AuthService
from cartrap.modules.admin.schemas import (
    AdminActionRequest,
    AdminActionResponse,
    AdminInviteListResponse,
    AdminOverviewResponse,
    AdminRuntimeSettingsResetRequest,
    AdminRuntimeSettingsResponse,
    AdminRuntimeSettingsUpdateRequest,
    AdminSystemHealthResponse,
    AdminUserDetailResponse,
    AdminUserDirectoryResponse,
)
from cartrap.modules.monitoring.job_runtime import JobRuntimeService
from cartrap.modules.admin.service import AdminService
from cartrap.modules.search.schemas import SearchCatalogResponse
from cartrap.modules.search.service import SearchService
from cartrap.modules.system_status.service import SystemStatusService
from cartrap.modules.watchlist.service import WatchlistService


router = APIRouter(prefix="/admin", tags=["admin"])


def get_search_service(request: Request) -> SearchService:
    provider_factory = getattr(request.app.state, "copart_provider_factory", None)
    runtime_settings_service = request.app.state.runtime_settings_service
    runtime_values = runtime_settings_service.get_effective_values(
        [
            "saved_search_poll_interval_minutes",
            "watchlist_default_poll_interval_minutes",
            "job_retry_backoff_seconds",
            "live_sync_stale_after_minutes",
        ]
    )
    system_status_service = SystemStatusService(
        request.app.state.mongo.database,
        live_sync_stale_after_minutes=int(runtime_values["live_sync_stale_after_minutes"]),
    )
    return SearchService(
        request.app.state.mongo.database,
        provider_factory=provider_factory,
        watchlist_service_factory=lambda: WatchlistService(
            request.app.state.mongo.database,
            provider_factory=provider_factory,
            default_poll_interval_minutes=int(runtime_values["watchlist_default_poll_interval_minutes"]),
            system_status_service=system_status_service,
        ),
        saved_search_poll_interval_minutes=int(runtime_values["saved_search_poll_interval_minutes"]),
        refresh_job_runtime=JobRuntimeService(
            request.app.state.mongo.database,
            retry_backoff_seconds=int(runtime_values["job_retry_backoff_seconds"]),
        ),
        system_status_service=system_status_service,
    )


def get_admin_service(request: Request) -> AdminService:
    return AdminService(
        request.app.state.mongo.database,
        settings=request.app.state.settings,
        runtime_settings_service=request.app.state.runtime_settings_service,
    )


@router.get("/overview", response_model=AdminOverviewResponse)
def get_admin_overview(
    current_user: dict = Depends(require_admin),
    admin_service: AdminService = Depends(get_admin_service),
) -> dict:
    del current_user
    return admin_service.get_overview()


@router.get("/system-health", response_model=AdminSystemHealthResponse)
def get_admin_system_health(
    current_user: dict = Depends(require_admin),
    admin_service: AdminService = Depends(get_admin_service),
) -> dict:
    del current_user
    return admin_service.get_system_health()


@router.get("/runtime-settings", response_model=AdminRuntimeSettingsResponse)
def get_admin_runtime_settings(
    current_user: dict = Depends(require_admin),
    admin_service: AdminService = Depends(get_admin_service),
) -> dict:
    del current_user
    return admin_service.get_runtime_settings()


@router.post("/runtime-settings", response_model=AdminRuntimeSettingsResponse)
def update_admin_runtime_settings(
    payload: AdminRuntimeSettingsUpdateRequest,
    current_user: dict = Depends(require_admin),
    admin_service: AdminService = Depends(get_admin_service),
) -> dict:
    return admin_service.update_runtime_settings(
        [item.model_dump() for item in payload.updates],
        updated_by=current_user["id"],
    )


@router.post("/runtime-settings/reset", response_model=AdminRuntimeSettingsResponse)
def reset_admin_runtime_settings(
    payload: AdminRuntimeSettingsResetRequest,
    current_user: dict = Depends(require_admin),
    admin_service: AdminService = Depends(get_admin_service),
) -> dict:
    del current_user
    return admin_service.reset_runtime_settings(payload.keys)


@router.get("/invites", response_model=AdminInviteListResponse)
def list_invites(
    current_user: dict = Depends(require_admin),
    admin_service: AdminService = Depends(get_admin_service),
) -> dict:
    del current_user
    return admin_service.list_invites()


@router.post("/invites", response_model=InviteResponse)
def create_invite(
    payload: InviteCreateRequest,
    current_user: dict = Depends(require_admin),
    auth_service: AuthService = Depends(get_auth_service),
) -> dict:
    return auth_service.create_invite(payload.email, current_user["id"])


@router.delete("/invites/{invite_id}", response_model=InviteResponse)
def revoke_invite(
    invite_id: str,
    current_user: dict = Depends(require_admin),
    auth_service: AuthService = Depends(get_auth_service),
) -> dict:
    del current_user
    return auth_service.revoke_invite(invite_id)


@router.get("/users", response_model=AdminUserDirectoryResponse)
def list_users(
    q: Optional[str] = Query(default=None),
    role: Optional[str] = Query(default="any"),
    status_filter: Optional[str] = Query(default="any", alias="status"),
    provider_state: Optional[str] = Query(default="any"),
    push_state: Optional[str] = Query(default="any"),
    saved_search_state: Optional[str] = Query(default="any"),
    watchlist_state: Optional[str] = Query(default="any"),
    last_login: Optional[str] = Query(default="any"),
    sort: str = Query(default="created_at_desc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    current_user: dict = Depends(require_admin),
    admin_service: AdminService = Depends(get_admin_service),
) -> dict:
    del current_user
    return admin_service.list_users(
        query=q,
        role=role,
        status_filter=status_filter,
        provider_state=provider_state,
        push_state=push_state,
        saved_search_state=saved_search_state,
        watchlist_state=watchlist_state,
        last_login=last_login,
        sort=sort,
        page=page,
        page_size=page_size,
    )


@router.get("/users/{user_id}", response_model=AdminUserDetailResponse)
def get_user_detail(
    user_id: str,
    current_user: dict = Depends(require_admin),
    admin_service: AdminService = Depends(get_admin_service),
) -> dict:
    del current_user
    return admin_service.get_user_detail(user_id)


@router.post("/users/{user_id}/actions/{action}", response_model=AdminActionResponse)
def run_user_action(
    user_id: str,
    action: str,
    payload: AdminActionRequest,
    current_user: dict = Depends(require_admin),
    admin_service: AdminService = Depends(get_admin_service),
) -> dict:
    del current_user
    return admin_service.execute_user_action(user_id, action, payload.model_dump())


@router.post("/search-catalog/refresh", response_model=SearchCatalogResponse)
def refresh_search_catalog(
    current_user: dict = Depends(require_admin),
    search_service: SearchService = Depends(get_search_service),
) -> dict:
    del current_user
    return search_service.refresh_catalog()
