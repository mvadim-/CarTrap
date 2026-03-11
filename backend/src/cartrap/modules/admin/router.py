"""Admin-only endpoints."""

from fastapi import APIRouter, Depends

from cartrap.api.dependencies import get_auth_service, require_admin
from cartrap.modules.auth.schemas import InviteCreateRequest, InviteResponse
from cartrap.modules.auth.service import AuthService


router = APIRouter(prefix="/admin", tags=["admin"])


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
