"""Pydantic schemas for manual search APIs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl, model_validator

from cartrap.modules.copart_provider.models import CopartApiSearchRequest
from cartrap.modules.copart_provider.models import CopartSearchResult
from cartrap.modules.watchlist.schemas import WatchlistCreateResponse


class SearchRequest(BaseModel):
    make: Optional[str] = Field(default=None, min_length=1, max_length=80)
    model: Optional[str] = Field(default=None, min_length=1, max_length=120)
    make_filter: Optional[str] = Field(default=None, min_length=1, max_length=500)
    model_filter: Optional[str] = Field(default=None, min_length=1, max_length=500)
    year_from: Optional[int] = Field(default=None, ge=1900, le=2100)
    year_to: Optional[int] = Field(default=None, ge=1900, le=2100)
    lot_number: Optional[str] = Field(default=None, min_length=1, max_length=32)

    @model_validator(mode="after")
    def validate_at_least_one_filter(self) -> "SearchRequest":
        if not self.make and not self.model and not self.make_filter and not self.model_filter and not self.lot_number:
            raise ValueError("Provide make/model or lot_number.")
        if self.year_from and self.year_to and self.year_from > self.year_to:
            raise ValueError("year_from must be less than or equal to year_to.")
        return self

    def to_api_request(self, now: Optional[datetime] = None) -> CopartApiSearchRequest:
        misc_filters = ["vehicle_type_code:VEHTYPE_V"]
        if self.year_from or self.year_to:
            lower = self.year_from or self.year_to
            upper = self.year_to or self.year_from
            misc_filters.append(f"lot_year:[{lower} TO {upper}]")
        if self.make_filter:
            misc_filters.append(self.make_filter.strip())
        elif self.make:
            misc_filters.append(f"lot_make_code:{self.make.strip().upper()}")
        if self.model_filter:
            misc_filters.append(self.model_filter.strip())
        elif self.model:
            model = self.model.strip().upper()
            misc_filters.append(f'lot_model_group:"{model}" OR lot_model_desc:"{model}"')
        if self.lot_number:
            normalized = "".join(char for char in self.lot_number if char.isdigit())
            misc_filters.append(f"lot_number:{normalized}")
        request_time = now or datetime.now(timezone.utc)
        start_of_day = request_time.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        return CopartApiSearchRequest(
            misc=misc_filters,
            sort=["salelight_priority asc", "auction_date_type desc", "auction_date_utc asc"],
            filter=[],
            local_filters=[],
            latlng_facets=False,
            page_number=1,
            user_start_utc_datetime=start_of_day.isoformat().replace("+00:00", "Z"),
        )


class SearchResultResponse(CopartSearchResult):
    pass


class SearchResponse(BaseModel):
    results: list[SearchResultResponse]
    source_request: dict


class SearchCatalogModelResponse(BaseModel):
    slug: str
    name: str
    search_filter: str


class SearchCatalogMakeResponse(BaseModel):
    slug: str
    name: str
    aliases: list[str] = []
    search_filter: str
    models: list[SearchCatalogModelResponse]


class SearchCatalogSummaryResponse(BaseModel):
    make_count: int
    model_count: int
    assigned_model_count: int
    exact_match_count: int
    fuzzy_match_count: int
    unassigned_model_count: int
    year_count: int


class SearchCatalogResponse(BaseModel):
    generated_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    summary: SearchCatalogSummaryResponse
    years: list[int]
    makes: list[SearchCatalogMakeResponse]
    manual_override_count: int = 0


class AddFromSearchRequest(BaseModel):
    lot_url: HttpUrl


class AddFromSearchResponse(WatchlistCreateResponse):
    pass
