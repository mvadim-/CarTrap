"""Admin-only endpoints."""

from fastapi import APIRouter, Depends, Request

from cartrap.api.dependencies import get_auth_service, require_admin
from cartrap.modules.auth.schemas import InviteCreateRequest, InviteResponse
from cartrap.modules.auth.service import AuthService
from cartrap.modules.search.schemas import SearchCatalogResponse
from cartrap.modules.search.service import SearchService
from cartrap.modules.watchlist.service import WatchlistService


router = APIRouter(prefix="/admin", tags=["admin"])


def get_search_service(request: Request) -> SearchService:
    provider_factory = getattr(request.app.state, "copart_provider_factory", None)
    return SearchService(
        request.app.state.mongo.database,
        provider_factory=provider_factory,
        watchlist_service_factory=lambda: WatchlistService(
            request.app.state.mongo.database,
            provider_factory=provider_factory,
        ),
    )


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


@router.post("/search-catalog/refresh", response_model=SearchCatalogResponse)
def refresh_search_catalog(
    current_user: dict = Depends(require_admin),
    search_service: SearchService = Depends(get_search_service),
) -> dict:
    del current_user
    return search_service.refresh_catalog()
