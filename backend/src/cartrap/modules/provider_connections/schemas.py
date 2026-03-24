"""Schemas for provider-connection APIs and shared diagnostics."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ProviderConnectionErrorResponse(BaseModel):
    code: str
    message: str
    retryable: bool = False
    occurred_at: Optional[datetime] = None


class ProviderConnectionBundleResponse(BaseModel):
    key_version: str
    captured_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None


class ProviderConnectionResponse(BaseModel):
    id: str
    provider: str
    status: str
    account_label: Optional[str] = None
    connected_at: Optional[datetime] = None
    disconnected_at: Optional[datetime] = None
    last_verified_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    reconnect_required: bool = False
    usable: bool = False
    bundle_version: int = 1
    bundle: Optional[ProviderConnectionBundleResponse] = None
    last_error: Optional[ProviderConnectionErrorResponse] = None
    created_at: datetime
    updated_at: datetime


class ProviderConnectionListResponse(BaseModel):
    items: list[ProviderConnectionResponse] = Field(default_factory=list)


class CopartConnectionRequest(BaseModel):
    username: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=255)


class ProviderConnectionMutationResponse(BaseModel):
    connection: ProviderConnectionResponse


class ProviderConnectionDiagnosticResponse(BaseModel):
    provider: str
    status: str
    message: str
    connection_id: Optional[str] = None
    reconnect_required: bool = False
