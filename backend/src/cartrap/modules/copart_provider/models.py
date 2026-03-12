"""Domain models for Copart API results."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, HttpUrl


class CopartApiSearchRequest(BaseModel):
    misc: list[str]
    sort: list[str]
    filter: list[str]
    local_filters: list[str]
    latlng_facets: bool
    page_number: int
    user_start_utc_datetime: str

    def to_payload(self) -> dict[str, Any]:
        return {
            "MISC": self.misc,
            "sort": self.sort,
            "filter": self.filter,
            "localFilters": self.local_filters,
            "latlngFacets": self.latlng_facets,
            "pageNumber": self.page_number,
            "userStartUtcDatetime": self.user_start_utc_datetime,
        }


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
