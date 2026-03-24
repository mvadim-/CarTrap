"""API routes for provider-connection management."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from cartrap.api.dependencies import get_current_user
from cartrap.modules.provider_connections.models import PROVIDER_COPART
from cartrap.modules.provider_connections.schemas import (
    CopartConnectionRequest,
    ProviderConnectionListResponse,
    ProviderConnectionMutationResponse,
)
from cartrap.modules.provider_connections.service import ProviderConnectionService


router = APIRouter(prefix="/provider-connections", tags=["provider-connections"])


def get_provider_connection_service(request: Request) -> ProviderConnectionService:
    connector_client_factory = getattr(request.app.state, "copart_connector_client_factory", None)
    return ProviderConnectionService(
        request.app.state.mongo.database,
        settings=request.app.state.settings,
        connector_client_factory=connector_client_factory,
    )


@router.get("", response_model=ProviderConnectionListResponse)
def list_provider_connections(
    current_user: dict = Depends(get_current_user),
    service: ProviderConnectionService = Depends(get_provider_connection_service),
) -> dict:
    return service.list_connections(current_user)


@router.post("/copart/connect", response_model=ProviderConnectionMutationResponse)
def connect_copart(
    payload: CopartConnectionRequest,
    current_user: dict = Depends(get_current_user),
    service: ProviderConnectionService = Depends(get_provider_connection_service),
) -> dict:
    return service.connect_copart(current_user, username=payload.username, password=payload.password)


@router.post("/copart/reconnect", response_model=ProviderConnectionMutationResponse)
def reconnect_copart(
    payload: CopartConnectionRequest,
    current_user: dict = Depends(get_current_user),
    service: ProviderConnectionService = Depends(get_provider_connection_service),
) -> dict:
    return service.reconnect_copart(current_user, username=payload.username, password=payload.password)


@router.delete(f"/{PROVIDER_COPART}", response_model=ProviderConnectionMutationResponse)
def disconnect_copart(
    current_user: dict = Depends(get_current_user),
    service: ProviderConnectionService = Depends(get_provider_connection_service),
) -> dict:
    return service.disconnect_copart(current_user)
