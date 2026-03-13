"""Pydantic schemas for manual search APIs."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlencode
from uuid import uuid4

from pydantic import BaseModel, Field, HttpUrl, model_validator

from cartrap.modules.copart_provider.models import CopartApiSearchRequest
from cartrap.modules.copart_provider.models import CopartSearchResult
from cartrap.modules.watchlist.schemas import WatchlistCreateResponse

DRIVE_TYPE_FILTER_VARIANTS = {
    "all_wheel_drive": ["ALL WHEEL DRIVE", "All Wheel Drive"],
    "front_wheel_drive": ["FRONT-WHEEL DRIVE", "Front-wheel Drive"],
    "rear_wheel_drive": ["REAR-WHEEL DRIVE", "Rear-wheel Drive"],
    "4x4_front": ["4X4 W/FRONT WHL DRV", "4x4 W/front Whl Drv"],
    "4x4_rear": ["4X4 W/REAR WHEEL DRV", "4x4 W/rear Wheel Drv"],
}

PRIMARY_DAMAGE_CODES = {
    "front_end": "DAMAGECODE_FR",
    "rear_end": "DAMAGECODE_RR",
    "side": "DAMAGECODE_SD",
    "hail": "DAMAGECODE_HL",
    "minor_dents_scratches": "DAMAGECODE_MN",
    "mechanical": "DAMAGECODE_MC",
    "water_flood": "DAMAGECODE_WA",
    "rollover": "DAMAGECODE_RO",
    "normal_wear": "DAMAGECODE_NW",
}

TITLE_TYPE_CODES = {
    "clean_title": "TITLEGROUP_C",
    "salvage_title": "TITLEGROUP_S",
    "non_repairable": "TITLEGROUP_J",
}

FUEL_TYPE_FILTER_VARIANTS = {
    "electric": ["ELECTRIC", "Electric"],
}

LOT_CONDITION_CODES = {
    "run_and_drive": "CERT-D",
    "enhanced_vehicles": "CERT-E",
    "engine_start_program": "CERT-S",
}

ODOMETER_RANGE_QUERIES = {
    "under_25000": "odometer_reading_received:[* TO 25000]",
    "25000_to_50000": "odometer_reading_received:[25000 TO 50000]",
    "50001_to_75000": "odometer_reading_received:[50001 TO 75000]",
    "75001_to_100000": "odometer_reading_received:[75001 TO 100000]",
    "100001_to_150000": "odometer_reading_received:[100001 TO 150000]",
    "150001_to_200000": "odometer_reading_received:[150001 TO 200000]",
    "over_200000": "odometer_reading_received:[200000 TO *]",
}


class SearchRequest(BaseModel):
    make: Optional[str] = Field(default=None, min_length=1, max_length=80)
    model: Optional[str] = Field(default=None, min_length=1, max_length=120)
    make_filter: Optional[str] = Field(default=None, min_length=1, max_length=500)
    model_filter: Optional[str] = Field(default=None, min_length=1, max_length=500)
    drive_type: Optional[str] = Field(default=None, min_length=1, max_length=40)
    primary_damage: Optional[str] = Field(default=None, min_length=1, max_length=40)
    title_type: Optional[str] = Field(default=None, min_length=1, max_length=40)
    fuel_type: Optional[str] = Field(default=None, min_length=1, max_length=40)
    lot_condition: Optional[str] = Field(default=None, min_length=1, max_length=40)
    odometer_range: Optional[str] = Field(default=None, min_length=1, max_length=40)
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
        structured_filters = self.build_structured_filters()
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
            filter=structured_filters,
            local_filters=[],
            latlng_facets=False,
            page_number=1,
            user_start_utc_datetime=start_of_day.isoformat().replace("+00:00", "Z"),
        )

    def normalized_criteria(self) -> dict:
        payload = self.model_dump(exclude_none=True)
        if "make" in payload:
            payload["make"] = str(payload["make"]).strip().upper()
        if "model" in payload:
            payload["model"] = str(payload["model"]).strip().upper()
        if "make_filter" in payload:
            payload["make_filter"] = str(payload["make_filter"]).strip()
        if "model_filter" in payload:
            payload["model_filter"] = str(payload["model_filter"]).strip()
        if "drive_type" in payload:
            payload["drive_type"] = str(payload["drive_type"]).strip().lower()
        if "primary_damage" in payload:
            payload["primary_damage"] = str(payload["primary_damage"]).strip().lower()
        if "title_type" in payload:
            payload["title_type"] = str(payload["title_type"]).strip().lower()
        if "fuel_type" in payload:
            payload["fuel_type"] = str(payload["fuel_type"]).strip().lower()
        if "lot_condition" in payload:
            payload["lot_condition"] = str(payload["lot_condition"]).strip().lower()
        if "odometer_range" in payload:
            payload["odometer_range"] = str(payload["odometer_range"]).strip().lower()
        if "lot_number" in payload:
            payload["lot_number"] = "".join(char for char in str(payload["lot_number"]) if char.isdigit())
        return payload

    def display_title(self) -> str:
        parts: list[str] = []
        if self.make:
            parts.append(self.make.strip().upper())
        if self.model:
            parts.append(self.model.strip().upper())
        if self.lot_number:
            parts.append(f"LOT {''.join(char for char in self.lot_number if char.isdigit())}")
        if self.year_from or self.year_to:
            lower = self.year_from or self.year_to
            upper = self.year_to or self.year_from
            parts.append(f"{lower}-{upper}")
        return " ".join(part for part in parts if part).strip() or "Saved Search"

    def build_structured_filters(self) -> list[str]:
        filters: list[str] = []
        if self.drive_type:
            drive_variants = DRIVE_TYPE_FILTER_VARIANTS.get(self.drive_type.strip().lower())
            if drive_variants:
                drive_filters = " OR ".join([f'drive:"{variant}"' for variant in drive_variants])
                filters.append(f"({drive_filters})")
        if self.primary_damage:
            damage_code = PRIMARY_DAMAGE_CODES.get(self.primary_damage.strip().lower())
            if damage_code:
                filters.append(f"(damage_type_code:{damage_code})")
        if self.title_type:
            title_code = TITLE_TYPE_CODES.get(self.title_type.strip().lower())
            if title_code:
                filters.append(f"(title_group_code:{title_code})")
        if self.fuel_type:
            fuel_variants = FUEL_TYPE_FILTER_VARIANTS.get(self.fuel_type.strip().lower())
            if fuel_variants:
                fuel_filters = " OR ".join([f'fuel_type_desc:"{variant}"' for variant in fuel_variants])
                filters.append(f"({fuel_filters})")
        if self.lot_condition:
            condition_code = LOT_CONDITION_CODES.get(self.lot_condition.strip().lower())
            if condition_code:
                filters.append(f"(lot_condition_code:{condition_code})")
        if self.odometer_range:
            odometer_query = ODOMETER_RANGE_QUERIES.get(self.odometer_range.strip().lower())
            if odometer_query:
                filters.append(f"({odometer_query})")
        return filters

    def to_external_url(self) -> str:
        if self.lot_number:
            normalized = "".join(char for char in self.lot_number if char.isdigit())
            if normalized:
                return f"https://www.copart.com/lot/{normalized}"

        query_text = self.display_title()
        search_filters: dict[str, list[str]] = {}
        if self.year_from or self.year_to:
            lower = self.year_from or self.year_to
            upper = self.year_to or self.year_from
            search_filters["YEAR"] = [f"lot_year:[{lower} TO {upper}]"]
        if self.make:
            search_filters["MAKE"] = [f'lot_make_desc:"{self.make.strip().upper()}"']
        elif self.make_filter:
            search_filters["MAKE"] = [self.make_filter.strip()]
        if self.model:
            search_filters["MODL"] = [f'lot_model_desc:"{self.model.strip().upper()}"']
        elif self.model_filter:
            search_filters["MODL"] = [self.model_filter.strip()]
        if self.drive_type:
            drive_variants = DRIVE_TYPE_FILTER_VARIANTS.get(self.drive_type.strip().lower())
            if drive_variants:
                search_filters["DRIV"] = [f'drive:"{drive_variants[0]}"']
        if self.primary_damage:
            damage_code = PRIMARY_DAMAGE_CODES.get(self.primary_damage.strip().lower())
            if damage_code:
                search_filters["DMG"] = [f"damage_type_code:{damage_code}"]
        if self.title_type:
            title_code = TITLE_TYPE_CODES.get(self.title_type.strip().lower())
            if title_code:
                search_filters["TITL"] = [f"title_group_code:{title_code}"]
        if self.fuel_type:
            fuel_variants = FUEL_TYPE_FILTER_VARIANTS.get(self.fuel_type.strip().lower())
            if fuel_variants:
                search_filters["FUEL"] = [f'fuel_type_desc:"{fuel_variants[0]}"']
        if self.lot_condition:
            condition_code = LOT_CONDITION_CODES.get(self.lot_condition.strip().lower())
            if condition_code:
                search_filters["COND"] = [f"lot_condition_code:{condition_code}"]
        if self.odometer_range:
            odometer_query = ODOMETER_RANGE_QUERIES.get(self.odometer_range.strip().lower())
            if odometer_query:
                search_filters["ODM"] = [odometer_query]

        search_criteria = {
            "query": [query_text] if query_text else ["*"],
            "filter": search_filters,
            "searchName": "",
            "watchListOnly": False,
            "freeFormSearch": True,
        }
        request_id = f"{uuid4()}-{int(datetime.now(timezone.utc).timestamp() * 1000)}"
        params = {
            "free": "true",
            "displayStr": query_text or "*",
            "from": "/vehicleFinder",
            "fromSource": "widget",
            "qId": request_id,
            "searchCriteria": json.dumps(search_criteria, separators=(",", ":")),
        }
        return f"https://www.copart.com/lotSearchResults?{urlencode(params)}"


class SearchResultResponse(CopartSearchResult):
    pass


class SearchResponse(BaseModel):
    results: list[SearchResultResponse]
    total_results: int = 0
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


class SavedSearchCreateRequest(SearchRequest):
    label: Optional[str] = Field(default=None, min_length=1, max_length=120)
    result_count: Optional[int] = Field(default=None, ge=0)


class SavedSearchResponse(BaseModel):
    id: str
    label: str
    criteria: SearchRequest
    external_url: HttpUrl
    result_count: Optional[int] = None
    created_at: datetime


class SavedSearchListResponse(BaseModel):
    items: list[SavedSearchResponse] = Field(default_factory=list)


class SavedSearchCreateResponse(BaseModel):
    saved_search: SavedSearchResponse


class AddFromSearchRequest(BaseModel):
    lot_url: HttpUrl


class AddFromSearchResponse(WatchlistCreateResponse):
    pass
