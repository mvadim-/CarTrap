"""Pydantic schemas for watchlist endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl


class WatchlistCreateRequest(BaseModel):
    lot_url: HttpUrl


class WatchlistItemResponse(BaseModel):
    id: str
    lot_number: str
    url: HttpUrl
    title: str
    status: str
    raw_status: str
    current_bid: Optional[float] = None
    buy_now_price: Optional[float] = None
    currency: str
    sale_date: Optional[datetime] = None
    last_checked_at: datetime
    created_at: datetime


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
