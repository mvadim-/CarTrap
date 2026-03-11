"""Pydantic schemas for manual search APIs."""

from __future__ import annotations

import json
from typing import Optional
from urllib.parse import urlencode

from pydantic import BaseModel, Field, HttpUrl, model_validator

from cartrap.modules.copart_provider.models import CopartSearchResult
from cartrap.modules.watchlist.schemas import WatchlistCreateResponse


class SearchRequest(BaseModel):
    search_url: Optional[HttpUrl] = None
    query: Optional[str] = Field(default=None, min_length=1, max_length=120)
    location: Optional[str] = Field(default=None, min_length=1, max_length=120)

    @model_validator(mode="after")
    def validate_at_least_one_filter(self) -> "SearchRequest":
        if not self.search_url and not self.query and not self.location:
            raise ValueError("Provide search_url or at least one filter.")
        return self

    def to_url(self) -> str:
        if self.search_url:
            return str(self.search_url)

        query_text = (self.query or "").strip()
        location_text = (self.location or "").strip()
        search_criteria = {
            "query": [query_text] if query_text else ["*"],
            "filter": {},
            "searchName": "",
            "watchListOnly": False,
            "freeFormSearch": True,
        }
        display_parts = [part for part in [query_text, location_text] if part]
        params = {
            "free": "true",
            "searchCriteria": json.dumps(search_criteria, separators=(",", ":")),
            "displayStr": ",".join(display_parts) if display_parts else "*",
            "from": "/vehicleFinder",
            "fromSource": "widget",
        }
        return f"https://www.copart.com/lotSearchResults?{urlencode(params)}"


class SearchResultResponse(CopartSearchResult):
    pass


class SearchResponse(BaseModel):
    results: list[SearchResultResponse]
    source_url: str


class AddFromSearchRequest(BaseModel):
    lot_url: HttpUrl


class AddFromSearchResponse(WatchlistCreateResponse):
    pass
