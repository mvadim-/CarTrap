"""Schemas for NAS Copart gateway proxy and connector endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, RootModel


class GatewaySearchRequest(RootModel[dict[str, Any]]):
    """Opaque search payload forwarded to Copart as-is."""


class GatewaySearchCountRequest(RootModel[dict[str, Any]]):
    """Opaque lightweight search-count payload forwarded to Copart as-is."""


class GatewayLotDetailsRequest(BaseModel):
    """Lot-details request payload."""

    model_config = ConfigDict(extra="ignore")

    lotNumber: int


class GatewayConnectorBootstrapRequest(BaseModel):
    username: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=255)


class GatewayEncryptedSessionBundlePayload(BaseModel):
    encrypted_bundle: str
    key_version: str
    captured_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None


class GatewayConnectorResponse(BaseModel):
    session_bundle: GatewayEncryptedSessionBundlePayload
    status: str
    verified_at: Optional[datetime] = None
    account_label: Optional[str] = None


class GatewayConnectorVerifyRequest(BaseModel):
    session_bundle: GatewayEncryptedSessionBundlePayload


class GatewayConnectorExecuteSearchRequest(BaseModel):
    session_bundle: GatewayEncryptedSessionBundlePayload
    search_payload: dict[str, Any]


class GatewayConnectorExecuteLotDetailsRequest(BaseModel):
    session_bundle: GatewayEncryptedSessionBundlePayload
    lot_number: int


class GatewayConnectorExecutionResponse(BaseModel):
    payload: Optional[dict[str, Any]] = None
    session_bundle: Optional[GatewayEncryptedSessionBundlePayload] = None
    status: str
    verified_at: Optional[datetime] = None
    used_at: Optional[datetime] = None
