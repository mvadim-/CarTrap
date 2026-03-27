"""Pydantic schemas for manual search APIs."""

from __future__ import annotations

import json
from datetime import datetime, timezone
import re
from typing import Optional
from urllib.parse import urlencode
from uuid import uuid4

from pydantic import BaseModel, Field, HttpUrl, model_validator

from cartrap.modules.auction_domain.models import (
    AuctionSearchResult,
    PROVIDER_COPART,
    SUPPORTED_AUCTION_PROVIDERS,
    get_auction_label,
    normalize_provider,
)
from cartrap.modules.copart_provider.models import CopartApiSearchRequest
from cartrap.modules.provider_connections.schemas import ProviderConnectionDiagnosticResponse
from cartrap.modules.system_status.schemas import FreshnessEnvelopeResponse, RefreshStateResponse
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

IAAI_DRIVE_TYPE_FACET_VALUES = {
    "all_wheel_drive": "All-Wheel Drive",
    "front_wheel_drive": "Front-Wheel Drive",
    "rear_wheel_drive": "Rear-Wheel Drive",
    "4x4_front": "4x4 W/Front Whl Drv",
    "4x4_rear": "4x4 W/Rear Wheel Drv",
}

IAAI_FUEL_TYPE_FACET_VALUES = {
    "electric": "Electric",
}

IAAI_PRIMARY_DAMAGE_FACET_VALUES = {
    "front_end": "Front End",
    "rear_end": "Rear",
    "side": "Side",
    "hail": "Hail",
    "minor_dents_scratches": "Minor Dents/Scratches",
    "mechanical": "Mechanical",
    "water_flood": "Flood",
    "rollover": "Rollover",
    "normal_wear": "Normal Wear",
}

IAAI_TITLE_TYPE_FACET_VALUES = {
    "clean_title": "Clear",
    "salvage_title": "Salvage",
    "non_repairable": "Non-Repairable",
}

IAAI_LOT_CONDITION_FACET_VALUES = {
    "run_and_drive": ("StartsDesc", "Run & Drive"),
}

IAAI_ODOMETER_RANGE_VALUES = {
    "under_25000": {"name": "ODOValue", "from": 0, "to": 25000},
    "25000_to_50000": {"name": "ODOValue", "from": 25000, "to": 50000},
    "50001_to_75000": {"name": "ODOValue", "from": 50001, "to": 75000},
    "75001_to_100000": {"name": "ODOValue", "from": 75001, "to": 100000},
    "100001_to_150000": {"name": "ODOValue", "from": 100001, "to": 150000},
    "150001_to_200000": {"name": "ODOValue", "from": 150001, "to": 200000},
    "over_200000": {"name": "ODOValue", "from": 200000},
}


class SearchRequest(BaseModel):
    providers: list[str] = Field(default_factory=lambda: [PROVIDER_COPART], min_length=1)
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
        normalized_providers: list[str] = []
        for provider in self.providers or [PROVIDER_COPART]:
            normalized = normalize_provider(provider)
            if normalized not in normalized_providers:
                normalized_providers.append(normalized)
        if not normalized_providers:
            raise ValueError("Provide at least one provider.")
        self.providers = normalized_providers
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

    def to_provider_payload(self, provider: str, now: Optional[datetime] = None) -> dict:
        normalized_provider = normalize_provider(provider)
        if normalized_provider == PROVIDER_COPART:
            return self.to_api_request(now=now).to_payload()
        return self.to_iaai_payload(now=now)

    def to_iaai_payload(self, now: Optional[datetime] = None) -> dict:
        request_time = now or datetime.now(timezone.utc)
        timestamp = request_time.astimezone(timezone.utc).strftime("%m/%d/%Y %I:%M:%S %p")
        searches = self._build_iaai_searches()
        if not searches:
            fallback_term = self._build_iaai_fallback_full_search()
            if fallback_term:
                searches = [{"fullSearch": fallback_term}]
        return {
            "returnFacets": False,
            "generateFacets": False,
            "zipCode": "",
            "pageSize": 100,
            "ShowRecommendations": False,
            "miles": 0,
            "useFastDistance": False,
            "sort": [{"isDescending": False, "isGeoSort": False, "sortField": "AuctionDateTime"}],
            "clientDateTimeInUtc": timestamp,
            "currentPage": 1,
            "returnAllIDs": False,
            "point": {"latitude": 0, "longitude": 0},
            "skipCaching": False,
            "roughGeoSearch": False,
            "includeReasoning": False,
            "IsSearchTimedAuction": False,
            "searches": searches,
            "includeLikeWords": True,
            "created": timestamp,
        }

    def normalized_criteria(self) -> dict:
        payload = self.model_dump(exclude_none=True)
        payload["providers"] = [normalize_provider(provider) for provider in payload.get("providers", [PROVIDER_COPART])]
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
        if self.providers and set(self.providers) != {PROVIDER_COPART}:
            parts.append("/".join(get_auction_label(provider) for provider in self.providers))
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

    def build_external_links(self) -> list[dict]:
        links: list[dict] = []
        for provider in self.providers:
            if provider == PROVIDER_COPART:
                links.append({"provider": provider, "label": get_auction_label(provider), "url": self.to_external_url()})
                continue
            query = self.display_title() or "vehicles"
            links.append(
                {
                    "provider": provider,
                    "label": get_auction_label(provider),
                    "url": f"https://www.iaai.com/Search?keyword={urlencode({'q': query})[2:]}",
                }
            )
        return links

    def _build_iaai_searches(self) -> list[dict[str, object]]:
        searches: list[dict[str, object]] = []
        lot_number = "".join(char for char in str(self.lot_number or "") if char.isdigit())
        if lot_number:
            searches.append({"fullSearch": lot_number})

        make_value = self._resolve_iaai_make_value()
        if make_value:
            searches.append(self._build_iaai_facet_search("Make", make_value))

        model_value = self._resolve_iaai_model_value()
        if model_value:
            searches.append(self._build_iaai_facet_search("Model", model_value))

        if self.year_from or self.year_to:
            lower = self.year_from or self.year_to
            upper = self.year_to or self.year_from
            if lower is not None and upper is not None:
                searches.append(self._build_iaai_long_range_search("Year", lower, upper))

        if self.drive_type:
            drive_value = IAAI_DRIVE_TYPE_FACET_VALUES.get(self.drive_type.strip().lower())
            if drive_value:
                searches.append(self._build_iaai_facet_search("DriveLineType", drive_value))

        if self.primary_damage:
            damage_value = IAAI_PRIMARY_DAMAGE_FACET_VALUES.get(self.primary_damage.strip().lower())
            if damage_value:
                searches.append(self._build_iaai_facet_search("PrimaryDamageDesc", damage_value))

        if self.title_type:
            title_value = IAAI_TITLE_TYPE_FACET_VALUES.get(self.title_type.strip().lower())
            if title_value:
                searches.append(self._build_iaai_facet_search("SaleDocument", title_value))

        if self.fuel_type:
            fuel_value = IAAI_FUEL_TYPE_FACET_VALUES.get(self.fuel_type.strip().lower())
            if fuel_value:
                searches.append(self._build_iaai_facet_search("FuelTypeDesc", fuel_value))

        if self.lot_condition:
            condition = IAAI_LOT_CONDITION_FACET_VALUES.get(self.lot_condition.strip().lower())
            if condition:
                group, value = condition
                searches.append(self._build_iaai_facet_search(group, value))

        if self.odometer_range:
            odometer_range = IAAI_ODOMETER_RANGE_VALUES.get(self.odometer_range.strip().lower())
            if odometer_range:
                searches.append({"longRanges": [odometer_range]})

        return searches

    def _build_iaai_fallback_full_search(self) -> Optional[str]:
        lot_number = "".join(char for char in str(self.lot_number or "") if char.isdigit())
        if lot_number:
            return lot_number
        parts = [self._resolve_iaai_make_value(), self._resolve_iaai_model_value()]
        fallback = " ".join(part for part in parts if part)
        return fallback or None

    def _resolve_iaai_make_value(self) -> Optional[str]:
        if self.make:
            return _normalize_iaai_make_value(self.make)
        parsed = _extract_catalog_filter_value(
            self.make_filter,
            ("lot_make_desc", "manufacturer_make_desc"),
        )
        return _normalize_iaai_make_value(parsed)

    def _resolve_iaai_model_value(self) -> Optional[str]:
        if self.model:
            return _normalize_iaai_text_value(self.model)
        return _extract_catalog_filter_value(
            self.model_filter,
            ("lot_model_desc", "lot_model_group", "manufacturer_model_desc"),
        )

    @staticmethod
    def _build_iaai_facet_search(group: str, value: str) -> dict[str, object]:
        return {"facets": [{"group": group, "value": value}]}

    @staticmethod
    def _build_iaai_long_range_search(name: str, lower: int, upper: int) -> dict[str, object]:
        return {"longRanges": [{"name": name, "from": lower, "to": upper}]}


def _extract_catalog_filter_value(filter_text: str | None, field_names: tuple[str, ...]) -> Optional[str]:
    if not filter_text:
        return None
    for field_name in field_names:
        match = re.search(rf'{re.escape(field_name)}:"([^"]+)"', filter_text)
        if match:
            return _normalize_iaai_text_value(match.group(1))
    match = re.search(r'"([^"]+)"', filter_text)
    if match:
        return _normalize_iaai_text_value(match.group(1))
    return None


def _normalize_iaai_make_value(value: str | None) -> Optional[str]:
    normalized = _normalize_iaai_text_value(value)
    if normalized is None:
        return None
    parts: list[str] = []
    for token in re.split(r"([ /-])", normalized):
        if token in {" ", "/", "-"}:
            parts.append(token)
            continue
        if not token:
            continue
        if token.isupper() and len(token) <= 3:
            parts.append(token)
            continue
        parts.append(token.title() if token.isupper() else token)
    return "".join(parts).strip() or None


def _normalize_iaai_text_value(value: str | None) -> Optional[str]:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


class SearchResultResponse(AuctionSearchResult):
    pass


class SearchResponse(BaseModel):
    results: list[SearchResultResponse]
    total_results: int = 0
    source_request: dict
    provider_diagnostics: list[ProviderConnectionDiagnosticResponse] = Field(default_factory=list)


class SavedSearchCachedResultResponse(SearchResultResponse):
    is_new: bool = False


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
    seed_results: list[SearchResultResponse] = Field(default_factory=list)


class SavedSearchResponse(BaseModel):
    id: str
    label: str
    criteria: SearchRequest
    external_url: Optional[HttpUrl] = None
    external_links: list[dict] = Field(default_factory=list)
    result_count: Optional[int] = None
    cached_result_count: Optional[int] = None
    new_count: int = 0
    last_synced_at: Optional[datetime] = None
    freshness: FreshnessEnvelopeResponse
    refresh_state: RefreshStateResponse
    connection_diagnostic: Optional[ProviderConnectionDiagnosticResponse] = None
    connection_diagnostics: list[ProviderConnectionDiagnosticResponse] = Field(default_factory=list)
    created_at: datetime


class SavedSearchListResponse(BaseModel):
    items: list[SavedSearchResponse] = Field(default_factory=list)


class SavedSearchCreateResponse(BaseModel):
    saved_search: SavedSearchResponse


class SavedSearchViewResponse(BaseModel):
    saved_search: SavedSearchResponse
    results: list[SavedSearchCachedResultResponse] = Field(default_factory=list)
    cached_result_count: int = 0
    new_count: int = 0
    last_synced_at: Optional[datetime] = None
    seen_at: Optional[datetime] = None


class AddFromSearchRequest(BaseModel):
    provider: str = Field(default=PROVIDER_COPART)
    provider_lot_id: Optional[str] = Field(default=None, min_length=1, max_length=64)
    lot_number: Optional[str] = Field(default=None, min_length=1, max_length=32)
    lot_url: Optional[HttpUrl] = None

    @model_validator(mode="after")
    def validate_identifier(self) -> "AddFromSearchRequest":
        self.provider = normalize_provider(self.provider)
        if not self.provider_lot_id and not self.lot_number and not self.lot_url:
            raise ValueError("Provide provider_lot_id, lot_number, or lot_url.")
        if not self.provider_lot_id:
            if self.provider == PROVIDER_COPART and self.lot_number:
                self.provider_lot_id = "".join(char for char in self.lot_number if char.isdigit())
            elif self.provider == PROVIDER_COPART and self.lot_url:
                self.provider_lot_id = "".join(char for char in str(self.lot_url) if char.isdigit())
            elif self.lot_number:
                self.provider_lot_id = str(self.lot_number).strip()
        return self


class AddFromSearchResponse(WatchlistCreateResponse):
    pass
