"""Domain models for IAAI provider responses."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from cartrap.modules.auction_domain.models import AuctionLotSnapshot, AuctionSearchResult


class IaaiSearchPage(BaseModel):
    results: list[AuctionSearchResult]
    num_found: int = 0


@dataclass
class IaaiLotFetchResult:
    snapshot: Optional[AuctionLotSnapshot]
    etag: Optional[str]
    not_modified: bool = False


@dataclass
class IaaiSearchCountFetchResult:
    num_found: Optional[int]
    etag: Optional[str]
    not_modified: bool = False


@dataclass
class IaaiSessionTokenState:
    access_token: str
    refresh_token: Optional[str]
    expires_at: Optional[datetime]
