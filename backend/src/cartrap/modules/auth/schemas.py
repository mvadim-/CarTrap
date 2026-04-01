"""Pydantic schemas for auth and admin flows."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=256)


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(min_length=16)


class TokenPairResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class InviteCreateRequest(BaseModel):
    email: EmailStr


class InviteAcceptRequest(BaseModel):
    token: str = Field(min_length=16)
    password: str = Field(min_length=8, max_length=256)


class InviteResponse(BaseModel):
    id: str
    email: EmailStr
    status: str
    token: str
    expires_at: datetime
    accepted_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    created_by: Optional[str] = None


class UserResponse(BaseModel):
    id: str
    email: EmailStr
    role: str
    status: str


class AdminManagedUserResponse(UserResponse):
    created_at: datetime
    updated_at: datetime
    last_login_at: Optional[datetime] = None


class InviteAcceptedResponse(BaseModel):
    user: UserResponse
