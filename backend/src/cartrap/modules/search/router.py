"""Manual search endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status

from cartrap.api.dependencies import get_current_user
from cartrap.modules.search.schemas import (
    AddFromSearchRequest,
    AddFromSearchResponse,
    SearchCatalogResponse,
    SearchRequest,
    SearchResponse,
)
from cartrap.modules.search.service import SearchService
from cartrap.modules.watchlist.service import WatchlistService


router = APIRouter(prefix="/search", tags=["search"])


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


@router.post("", response_model=SearchResponse)
def search_lots(
    payload: SearchRequest,
    current_user: dict = Depends(get_current_user),
    search_service: SearchService = Depends(get_search_service),
) -> dict:
    del current_user
    return search_service.search(payload)


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
