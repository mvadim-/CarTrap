"""Shared FastAPI dependencies."""

from __future__ import annotations

from collections.abc import Callable
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from cartrap.modules.auth.service import AuthService
from cartrap.modules.runtime_settings.service import RuntimeSettingsService


bearer_scheme = HTTPBearer(auto_error=False)


def set_service_factory(app, factory: Callable[[], AuthService]) -> None:
    app.state.auth_service_factory = factory


def get_auth_service(request: Request) -> AuthService:
    factory = getattr(request.app.state, "auth_service_factory", None)
    if factory is None:
        raise RuntimeError("Auth service factory is not configured.")
    return factory()


def get_runtime_settings_service(request: Request) -> RuntimeSettingsService:
    service = getattr(request.app.state, "runtime_settings_service", None)
    if service is None:
        raise RuntimeError("Runtime settings service is not configured.")
    return service


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    auth_service: AuthService = Depends(get_auth_service),
) -> dict:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")

    return auth_service.get_current_user(credentials.credentials)


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required.")
    return user
