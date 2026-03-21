"""Manual search endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status

from cartrap.api.dependencies import get_current_user
from cartrap.modules.search.schemas import (
    AddFromSearchRequest,
    AddFromSearchResponse,
    SavedSearchCreateRequest,
    SavedSearchCreateResponse,
    SavedSearchListResponse,
    SavedSearchViewResponse,
    SearchCatalogResponse,
    SearchRequest,
    SearchResponse,
)
from cartrap.modules.search.service import SearchService
from cartrap.modules.watchlist.service import WatchlistService


router = APIRouter(prefix="/search", tags=["search"])


def get_search_service(request: Request) -> SearchService:
    provider_factory = getattr(request.app.state, "copart_provider_factory", None)
    settings = request.app.state.settings
    return SearchService(
        request.app.state.mongo.database,
        provider_factory=provider_factory,
        watchlist_service_factory=lambda: WatchlistService(
            request.app.state.mongo.database,
            provider_factory=provider_factory,
            default_poll_interval_minutes=settings.watchlist_default_poll_interval_minutes,
        ),
        saved_search_poll_interval_minutes=settings.saved_search_poll_interval_minutes,
    )


@router.post("", response_model=SearchResponse)
def search_lots(
    payload: SearchRequest,
    current_user: dict = Depends(get_current_user),
    search_service: SearchService = Depends(get_search_service),
) -> dict:
    del current_user
    return search_service.search(payload)


@router.get("/saved", response_model=SavedSearchListResponse)
def list_saved_searches(
    current_user: dict = Depends(get_current_user),
    search_service: SearchService = Depends(get_search_service),
) -> dict:
    return search_service.list_saved_searches(current_user)


@router.post("/saved", response_model=SavedSearchCreateResponse, status_code=status.HTTP_201_CREATED)
def save_search(
    payload: SavedSearchCreateRequest,
    current_user: dict = Depends(get_current_user),
    search_service: SearchService = Depends(get_search_service),
) -> dict:
    return search_service.save_search(current_user, payload)


@router.post("/saved/{saved_search_id}/view", response_model=SavedSearchViewResponse)
def view_saved_search(
    saved_search_id: str,
    current_user: dict = Depends(get_current_user),
    search_service: SearchService = Depends(get_search_service),
) -> dict:
    return search_service.view_saved_search(current_user, saved_search_id)


@router.post("/saved/{saved_search_id}/refresh-live", response_model=SavedSearchViewResponse)
def refresh_saved_search_live(
    saved_search_id: str,
    current_user: dict = Depends(get_current_user),
    search_service: SearchService = Depends(get_search_service),
) -> dict:
    return search_service.refresh_saved_search_live(current_user, saved_search_id)


@router.delete("/saved/{saved_search_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_saved_search(
    saved_search_id: str,
    current_user: dict = Depends(get_current_user),
    search_service: SearchService = Depends(get_search_service),
) -> None:
    search_service.remove_saved_search(current_user, saved_search_id)


@router.get("/catalog", response_model=SearchCatalogResponse)
def get_search_catalog(
    current_user: dict = Depends(get_current_user),
    search_service: SearchService = Depends(get_search_service),
) -> dict:
    del current_user
    return search_service.get_catalog()


@router.post("/watchlist", response_model=AddFromSearchResponse, status_code=status.HTTP_201_CREATED)
def add_from_search(
    payload: AddFromSearchRequest,
    current_user: dict = Depends(get_current_user),
    search_service: SearchService = Depends(get_search_service),
) -> dict:
    return search_service.add_from_search(current_user, str(payload.lot_url))
