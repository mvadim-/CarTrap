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
    AdminSystemHealthResponse,
    AdminUserDetailResponse,
    AdminUserDirectoryResponse,
)
from cartrap.modules.admin.service import AdminService
from cartrap.modules.search.schemas import SearchCatalogResponse
from cartrap.modules.search.service import SearchService
from cartrap.modules.watchlist.service import WatchlistService


router = APIRouter(prefix="/admin", tags=["admin"])


def get_search_service(request: Request) -> SearchService:
    provider_factory = getattr(request.app.state, "copart_provider_factory", None)
    settings = request.app.state.settings
    return SearchService(
        request.app.state.mongo.database,
        provider_factory=provider_factory,
        watchlist_service_factory=lambda: WatchlistService(
            request.app.state.mongo.database,
            provider_factory=provider_factory,
        ),
        saved_search_poll_interval_minutes=settings.saved_search_poll_interval_minutes,
    )


def get_admin_service(request: Request) -> AdminService:
    return AdminService(
        request.app.state.mongo.database,
        settings=request.app.state.settings,
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
