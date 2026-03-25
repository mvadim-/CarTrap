"""Domain models for Copart API results."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel

from cartrap.modules.auction_domain.models import AuctionLotSnapshot, AuctionSearchResult, PROVIDER_COPART, get_auction_label


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


class CopartLotSnapshot(AuctionLotSnapshot):
    provider: str = PROVIDER_COPART
    auction_label: str = get_auction_label(PROVIDER_COPART)


class CopartSearchResult(AuctionSearchResult):
    provider: str = PROVIDER_COPART
    auction_label: str = get_auction_label(PROVIDER_COPART)


class CopartSearchPage(BaseModel):
    results: list[CopartSearchResult]
    num_found: int = 0


@dataclass
class CopartLotFetchResult:
    snapshot: Optional[CopartLotSnapshot]
    etag: Optional[str]
    not_modified: bool = False


@dataclass
class CopartSearchCountFetchResult:
    num_found: Optional[int]
    etag: Optional[str]
    not_modified: bool = False
