"""Shared auction-domain identity helpers and normalized lot models."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, HttpUrl, model_validator


PROVIDER_COPART = "copart"
PROVIDER_IAAI = "iaai"

SUPPORTED_AUCTION_PROVIDERS = (PROVIDER_COPART, PROVIDER_IAAI)
AUCTION_LABELS = {
    PROVIDER_COPART: "Copart",
    PROVIDER_IAAI: "IAAI",
}


def normalize_provider(provider: Optional[str]) -> str:
    normalized = str(provider or PROVIDER_COPART).strip().lower()
    if normalized not in SUPPORTED_AUCTION_PROVIDERS:
        raise ValueError(f"Unsupported auction provider: {provider}")
    return normalized


def get_auction_label(provider: Optional[str]) -> str:
    return AUCTION_LABELS[normalize_provider(provider)]


def build_lot_key(
    provider: Optional[str],
    provider_lot_id: Optional[str] = None,
    lot_number: Optional[str] = None,
) -> str:
    normalized_provider = normalize_provider(provider)
    reference = str(provider_lot_id or lot_number or "").strip()
    if not reference:
        raise ValueError("provider_lot_id or lot_number is required to build lot_key.")
    return f"{normalized_provider}:{reference}"


def backfill_lot_identity(payload: dict[str, Any], *, default_provider: str = PROVIDER_COPART) -> dict[str, Any]:
    document = dict(payload)
    provider = normalize_provider(document.get("provider") or default_provider)
    lot_number = str(document.get("lot_number") or "").strip() or None
    provider_lot_id = str(document.get("provider_lot_id") or lot_number or "").strip() or None
    if provider_lot_id is None:
        raise ValueError("Legacy lot payload does not contain provider_lot_id or lot_number.")
    document["provider"] = provider
    document["auction_label"] = str(document.get("auction_label") or get_auction_label(provider))
    document["provider_lot_id"] = provider_lot_id
    document["lot_key"] = str(document.get("lot_key") or build_lot_key(provider, provider_lot_id, lot_number))
    return document


class AuctionSearchResult(BaseModel):
    provider: str = Field(default=PROVIDER_COPART)
    auction_label: Optional[str] = None
    provider_lot_id: Optional[str] = None
    lot_key: Optional[str] = None
    lot_number: str
    title: str
    url: Optional[HttpUrl] = None
    thumbnail_url: Optional[HttpUrl] = None
    location: Optional[str] = None
    odometer: Optional[str] = None
    sale_date: Optional[datetime] = None
    current_bid: Optional[float] = None
    buy_now_price: Optional[float] = None
    currency: str = "USD"
    status: str = "upcoming"
    raw_status: str = "upcoming"
    provider_metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def finalize_identity(self) -> "AuctionSearchResult":
        self.provider = normalize_provider(self.provider)
        if not self.auction_label:
            self.auction_label = get_auction_label(self.provider)
        if not self.provider_lot_id:
            self.provider_lot_id = str(self.lot_number)
        if not self.lot_key:
            self.lot_key = build_lot_key(self.provider, self.provider_lot_id, self.lot_number)
        return self


class AuctionLotSnapshot(BaseModel):
    provider: str = Field(default=PROVIDER_COPART)
    auction_label: Optional[str] = None
    provider_lot_id: Optional[str] = None
    lot_key: Optional[str] = None
    lot_number: str
    title: str
    url: Optional[HttpUrl] = None
    thumbnail_url: Optional[HttpUrl] = None
    image_urls: list[HttpUrl] = Field(default_factory=list)
    odometer: Optional[str] = None
    primary_damage: Optional[str] = None
    estimated_retail_value: Optional[float] = None
    has_key: Optional[bool] = None
    drivetrain: Optional[str] = None
    highlights: list[str] = Field(default_factory=list)
    vin: Optional[str] = None
    status: str
    sale_date: Optional[datetime] = None
    current_bid: Optional[float] = None
    buy_now_price: Optional[float] = None
    currency: str = "USD"
    raw_status: str
    provider_metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def finalize_identity(self) -> "AuctionLotSnapshot":
        self.provider = normalize_provider(self.provider)
        if not self.auction_label:
            self.auction_label = get_auction_label(self.provider)
        if not self.provider_lot_id:
            self.provider_lot_id = str(self.lot_number)
        if not self.lot_key:
            self.lot_key = build_lot_key(self.provider, self.provider_lot_id, self.lot_number)
        return self
