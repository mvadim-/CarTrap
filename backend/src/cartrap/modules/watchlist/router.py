"""Watchlist API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status

from cartrap.api.dependencies import get_current_user
from cartrap.modules.watchlist.schemas import (
    WatchlistCreateRequest,
    WatchlistCreateResponse,
    WatchlistListResponse,
    WatchlistRefreshResponse,
)
from cartrap.modules.watchlist.service import WatchlistService


router = APIRouter(prefix="/watchlist", tags=["watchlist"])


def get_watchlist_service(request: Request) -> WatchlistService:
    provider_factory = getattr(request.app.state, "copart_provider_factory", None)
    settings = request.app.state.settings
    return WatchlistService(
        request.app.state.mongo.database,
        provider_factory=provider_factory,
        default_poll_interval_minutes=settings.watchlist_default_poll_interval_minutes,
    )


@router.get("", response_model=WatchlistListResponse)
def list_watchlist(
    current_user: dict = Depends(get_current_user),
    watchlist_service: WatchlistService = Depends(get_watchlist_service),
) -> dict:
    return watchlist_service.list_watchlist(current_user)


@router.post("", response_model=WatchlistCreateResponse, status_code=status.HTTP_201_CREATED)
def add_to_watchlist(
    payload: WatchlistCreateRequest,
    current_user: dict = Depends(get_current_user),
    watchlist_service: WatchlistService = Depends(get_watchlist_service),
) -> dict:
    return watchlist_service.add_tracked_lot(current_user, payload.to_lot_url())


@router.post("/{tracked_lot_id}/refresh-live", response_model=WatchlistRefreshResponse)
def refresh_watchlist_lot_live(
    tracked_lot_id: str,
    current_user: dict = Depends(get_current_user),
    watchlist_service: WatchlistService = Depends(get_watchlist_service),
) -> dict:
    return watchlist_service.refresh_tracked_lot_live(current_user, tracked_lot_id)


@router.delete("/{tracked_lot_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_from_watchlist(
    tracked_lot_id: str,
    current_user: dict = Depends(get_current_user),
    watchlist_service: WatchlistService = Depends(get_watchlist_service),
) -> None:
    watchlist_service.remove_tracked_lot(current_user, tracked_lot_id)
