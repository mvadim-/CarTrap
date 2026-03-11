"""Domain models for Copart scraping results."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, HttpUrl


class CopartLotSnapshot(BaseModel):
    lot_number: str
    title: str
    url: HttpUrl
    status: str
    sale_date: Optional[datetime] = None
    current_bid: Optional[float] = None
    buy_now_price: Optional[float] = None
    currency: str = "USD"
    raw_status: str


class CopartSearchResult(BaseModel):
    lot_number: str
    title: str
    url: HttpUrl
    location: Optional[str] = None
    sale_date: Optional[datetime] = None
    current_bid: Optional[float] = None
    currency: str = "USD"
    status: str = "upcoming"
