"""Pydantic schemas for watchlist endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, HttpUrl, model_validator

from cartrap.modules.provider_connections.schemas import ProviderConnectionDiagnosticResponse
from cartrap.modules.system_status.schemas import FreshnessEnvelopeResponse, RefreshStateResponse


class WatchlistCreateRequest(BaseModel):
    lot_url: Optional[HttpUrl] = None
    lot_number: Optional[str] = Field(default=None, min_length=1, max_length=32)

    @model_validator(mode="after")
    def validate_identifier(self) -> "WatchlistCreateRequest":
        if not self.lot_url and not self.lot_number:
            raise ValueError("Provide lot_url or lot_number.")
        if self.lot_number and not any(char.isdigit() for char in self.lot_number):
            raise ValueError("Lot number must contain digits.")
        return self

    def to_lot_url(self) -> str:
        if self.lot_url:
            return str(self.lot_url)
        normalized = "".join(char for char in str(self.lot_number) if char.isdigit())
        return f"https://www.copart.com/lot/{normalized}"


class LotChangeValueResponse(BaseModel):
    before: Any = None
    after: Any = None


class WatchlistItemResponse(BaseModel):
    id: str
    lot_number: str
    url: HttpUrl
    title: str
    thumbnail_url: Optional[HttpUrl] = None
    image_urls: list[HttpUrl] = []
    odometer: Optional[str] = None
    primary_damage: Optional[str] = None
    estimated_retail_value: Optional[float] = None
    has_key: Optional[bool] = None
    drivetrain: Optional[str] = None
    highlights: list[str] = Field(default_factory=list)
    vin: Optional[str] = None
    status: str
    raw_status: str
    current_bid: Optional[float] = None
    buy_now_price: Optional[float] = None
    currency: str
    sale_date: Optional[datetime] = None
    last_checked_at: datetime
    freshness: FreshnessEnvelopeResponse
    refresh_state: RefreshStateResponse
    connection_diagnostic: Optional[ProviderConnectionDiagnosticResponse] = None
    created_at: datetime
    has_unseen_update: bool = False
    latest_change_at: Optional[datetime] = None
    latest_changes: dict[str, LotChangeValueResponse] = Field(default_factory=dict)


class LotSnapshotResponse(BaseModel):
    id: str
    tracked_lot_id: str
    lot_number: str
    status: str
    raw_status: str
    current_bid: Optional[float] = None
    buy_now_price: Optional[float] = None
    currency: str
    sale_date: Optional[datetime] = None
    detected_at: datetime


class WatchlistCreateResponse(BaseModel):
    tracked_lot: WatchlistItemResponse
    initial_snapshot: LotSnapshotResponse


class WatchlistListResponse(BaseModel):
    items: list[WatchlistItemResponse] = Field(default_factory=list)


class WatchlistRefreshResponse(BaseModel):
    tracked_lot: WatchlistItemResponse
