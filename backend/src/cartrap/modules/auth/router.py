"""Authentication endpoints."""

from fastapi import APIRouter, Depends, status

from cartrap.api.dependencies import get_auth_service
from cartrap.modules.auth.schemas import (
    InviteAcceptRequest,
    InviteAcceptedResponse,
    LoginRequest,
    RefreshTokenRequest,
    TokenPairResponse,
)
from cartrap.modules.auth.service import AuthService


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenPairResponse)
def login(payload: LoginRequest, auth_service: AuthService = Depends(get_auth_service)) -> dict:
    return auth_service.login(str(payload.email), payload.password)


@router.post("/refresh", response_model=TokenPairResponse)
def refresh_tokens(
    payload: RefreshTokenRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> dict:
    return auth_service.refresh_tokens(payload.refresh_token)


@router.post(
    "/invites/accept",
    response_model=InviteAcceptedResponse,
    status_code=status.HTTP_201_CREATED,
)
def accept_invite(
    payload: InviteAcceptRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> dict:
    return {"user": auth_service.accept_invite(payload.token, payload.password)}
