"""Watchlist API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status

from cartrap.api.dependencies import get_current_user
from cartrap.modules.provider_connections.service import ProviderConnectionService
from cartrap.modules.watchlist.schemas import (
    WatchlistAcknowledgeResponse,
    WatchlistCreateRequest,
    WatchlistCreateResponse,
    WatchlistListResponse,
    WatchlistRefreshResponse,
)
from cartrap.modules.watchlist.service import WatchlistService


router = APIRouter(prefix="/watchlist", tags=["watchlist"])


def get_watchlist_service(request: Request) -> WatchlistService:
    provider_factories: dict[str, object] = {}
    connector_client_factories: dict[str, object] = {}
    provider_factory = getattr(request.app.state, "copart_provider_factory", None)
    iaai_provider_factory = getattr(request.app.state, "iaai_provider_factory", None)
    connector_client_factory = getattr(request.app.state, "copart_connector_client_factory", None)
    iaai_connector_client_factory = getattr(request.app.state, "iaai_connector_client_factory", None)
    if provider_factory is not None:
        provider_factories["copart"] = provider_factory
    if iaai_provider_factory is not None:
        provider_factories["iaai"] = iaai_provider_factory
    if connector_client_factory is not None:
        connector_client_factories["copart"] = connector_client_factory
    if iaai_connector_client_factory is not None:
        connector_client_factories["iaai"] = iaai_connector_client_factory
    settings = request.app.state.settings
    return WatchlistService(
        request.app.state.mongo.database,
        provider_factory=provider_factory,
        provider_factories=provider_factories,
        provider_connection_service=ProviderConnectionService(
            request.app.state.mongo.database,
            settings=settings,
            connector_client_factories=connector_client_factories,
        ),
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
    return watchlist_service.add_tracked_lot(
        current_user,
        provider=payload.provider,
        provider_lot_id=payload.provider_lot_id,
        lot_reference=payload.to_lot_reference(),
    )


@router.post("/{tracked_lot_id}/refresh-live", response_model=WatchlistRefreshResponse)
def refresh_watchlist_lot_live(
    tracked_lot_id: str,
    current_user: dict = Depends(get_current_user),
    watchlist_service: WatchlistService = Depends(get_watchlist_service),
) -> dict:
    return watchlist_service.refresh_tracked_lot_live(current_user, tracked_lot_id)


@router.post("/{tracked_lot_id}/acknowledge-update", response_model=WatchlistAcknowledgeResponse)
def acknowledge_watchlist_lot_update(
    tracked_lot_id: str,
    current_user: dict = Depends(get_current_user),
    watchlist_service: WatchlistService = Depends(get_watchlist_service),
) -> dict:
    return watchlist_service.acknowledge_tracked_lot_update(current_user, tracked_lot_id)


@router.delete("/{tracked_lot_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_from_watchlist(
    tracked_lot_id: str,
    current_user: dict = Depends(get_current_user),
    watchlist_service: WatchlistService = Depends(get_watchlist_service),
) -> None:
    watchlist_service.remove_tracked_lot(current_user, tracked_lot_id)
