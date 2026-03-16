"""Schemas for NAS Copart gateway proxy endpoints."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, RootModel


class GatewaySearchRequest(RootModel[dict[str, Any]]):
    """Opaque search payload forwarded to Copart as-is."""


class GatewaySearchCountRequest(RootModel[dict[str, Any]]):
    """Opaque lightweight search-count payload forwarded to Copart as-is."""


class GatewayLotDetailsRequest(BaseModel):
    """Lot-details request payload."""

    model_config = ConfigDict(extra="ignore")

    lotNumber: int
