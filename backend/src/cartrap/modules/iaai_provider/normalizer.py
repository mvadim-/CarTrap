"""Normalization helpers for IAAI mobile payloads."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
import re
from urllib.parse import quote

from cartrap.modules.auction_domain.models import (
    AuctionLotSnapshot,
    AuctionSearchResult,
    PROVIDER_IAAI,
    get_auction_label,
)


IAAI_URL_TEMPLATE = "https://www.iaai.com/VehicleDetail/{provider_lot_id}"
STATUS_MAPPING = {
    "pre-bid": "upcoming",
    "prebid": "upcoming",
    "live": "live",
    "sold": "sold",
    "run & drive": "run_and_drive",
    "buy now": "buy_now",
    "auction closed": "closed",
}


def build_iaai_lot_url(provider_lot_id: str) -> str:
    return IAAI_URL_TEMPLATE.format(provider_lot_id=str(provider_lot_id).strip())


def extract_search_vehicles(payload: dict[str, Any]) -> list[dict[str, Any]]:
    for container in (payload, payload.get("result")):
        if not isinstance(container, dict):
            continue
        vehicles = container.get("vehicles")
        if isinstance(vehicles, list):
            return [item for item in vehicles if isinstance(item, dict)]
        results = container.get("results")
        if not isinstance(results, list):
            continue
        extracted: list[dict[str, Any]] = []
        for item in results:
            if not isinstance(item, dict):
                continue
            candidate = item.get("data") if isinstance(item.get("data"), dict) else item
            if not isinstance(candidate, dict):
                continue
            if any(field_name in candidate for field_name in ("id", "inventoryId", "itemId", "stockNumber", "make", "model")):
                extracted.append(candidate)
        if extracted:
            return extracted
    raise ValueError("IAAI search payload is missing 'vehicles'.")


def extract_search_total(payload: dict[str, Any]) -> int:
    for field_name in ("totalCount", "totalRecords", "vehicleCount"):
        value = payload.get(field_name)
        try:
            if value is not None:
                return max(0, int(value))
        except (TypeError, ValueError):
            continue
    vehicles = payload.get("vehicles")
    return len(vehicles) if isinstance(vehicles, list) else 0


def normalize_search_results(payload: list[dict[str, Any]]) -> list[AuctionSearchResult]:
    results: list[AuctionSearchResult] = []
    for item in payload:
        provider_lot_id = str(first_present(item, "id", "inventoryId", "itemId"))
        lot_number = str(first_present(item, "stockNumber", "itemId", "id"))
        raw_status = derive_raw_status(item)
        location = " ".join(
            value
            for value in [
                normalize_text(first_present(item, "branchName")),
                normalize_text(first_present(item, "city")),
                normalize_text(first_present(item, "state")),
            ]
            if value
        )
        results.append(
            AuctionSearchResult(
                provider=PROVIDER_IAAI,
                auction_label=get_auction_label(PROVIDER_IAAI),
                provider_lot_id=provider_lot_id,
                lot_key=None,
                lot_number=lot_number,
                title=build_search_result_title(item) or "Unknown lot",
                url=build_iaai_lot_url(provider_lot_id),
                thumbnail_url=normalize_text(first_present(item, "vehiclePrimaryImageUrl", "thumbnailUrl")),
                location=location or normalize_text(first_present(item, "market")),
                odometer=normalize_text(first_present(item, "odoValue", "odometer")),
                sale_date=parse_datetime(first_present(item, "auctionDateTime", "saleDate")),
                current_bid=parse_money(first_present(item, "currentBidAmount", "currentBid")),
                buy_now_price=extract_buy_now_price(item),
                currency=str(first_present(item, "currency") or "USD"),
                status=normalize_status(raw_status),
                raw_status=raw_status,
                provider_metadata={
                    "market": normalize_text(first_present(item, "market")),
                    "branch_name": normalize_text(first_present(item, "branchName")),
                    "item_id": normalize_text(first_present(item, "itemId")),
                },
            )
        )
    return results


def build_search_result_title(payload: dict[str, Any]) -> Optional[str]:
    return normalize_text(
        first_present(payload, "yearMakeModelSeries", "yearMakeModel", "description", "itemDescription")
        or compose_search_title_from_parts(payload)
        or first_present(payload, "title", "saleDocument")
    )


def compose_search_title_from_parts(payload: dict[str, Any]) -> Optional[str]:
    title_parts = [
        normalize_text(first_present(payload, "year")),
        normalize_text(first_present(payload, "make")),
        normalize_text(first_present(payload, "model")),
        normalize_text(first_present(payload, "series", "seriesName")),
    ]
    composed = " ".join(part for part in title_parts if part and part != "-")
    return composed or None


def normalize_lot_details_payload(payload: dict[str, Any]) -> AuctionLotSnapshot:
    inventory_result = resolve_inventory_result(payload)
    if inventory_result is None:
        raise ValueError("IAAI lot payload is missing 'inventoryResult'.")
    auction_information_raw = resolve_auction_information(payload) or {}
    sale_information = merge_field_maps(
        flatten_field_map(inventory_result.get("saleInformation")),
        flatten_field_map(auction_information_raw.get("saleInformation")),
    )
    bidding_information = merge_field_maps(
        flatten_field_map(inventory_result.get("biddingInformation")),
        flatten_field_map(auction_information_raw.get("biddingInformation")),
    )
    prebid_information = merge_field_maps(
        flatten_field_map(inventory_result.get("prebidInformation")),
        flatten_field_map(auction_information_raw.get("prebidInformation")),
    )
    vehicle_information = flatten_field_map(inventory_result.get("vehicleInformation"))
    vehicle_description = flatten_field_map(inventory_result.get("vehicleDescription"))
    attributes = flatten_field_map(inventory_result.get("attributes"))
    inventory_fields = merge_field_maps(
        flatten_field_map(inventory_result),
        flatten_field_map(auction_information_raw),
    )
    provider_lot_id = str(
        first_present(attributes, "Id", "inventoryId", "SalvageId")
        or first_present(inventory_fields, "inventoryId", "Id", "SalvageId", "id", "itemId")
    )
    lot_number = str(
        first_present(vehicle_information, "stockNumber", "StockHash", "StockNumber", "itemId", "lotNumber")
        or first_present(attributes, "StockNumber")
        or first_present(inventory_fields, "stockNumber", "StockNumber", "itemId", "lotNumber")
    )
    raw_status = derive_raw_status(
        {
            **inventory_fields,
            **sale_information,
            **vehicle_information,
            **vehicle_description,
            **attributes,
        }
    )
    image_urls = extract_image_urls(payload)
    thumbnail_url = extract_thumbnail_url(payload) or (image_urls[0] if image_urls else None)
    return AuctionLotSnapshot(
        provider=PROVIDER_IAAI,
        auction_label=get_auction_label(PROVIDER_IAAI),
        provider_lot_id=provider_lot_id,
        lot_number=lot_number,
        title=build_lot_title(vehicle_information, vehicle_description, attributes, inventory_fields) or "Unknown lot",
        url=build_iaai_lot_url(provider_lot_id),
        thumbnail_url=thumbnail_url or normalize_text(first_present(payload, "vehiclePrimaryImageUrl")),
        image_urls=image_urls,
        odometer=normalize_text(
            first_present(vehicle_information, "Odometer", "odometer", "odoValue")
            or first_present(attributes, "ODOValue")
            or first_present(inventory_fields, "odometer", "odoValue")
        ),
        primary_damage=normalize_text(
            first_present(vehicle_information, "PrimaryDamage", "primaryDamage", "Primary Damage")
            or first_present(attributes, "PrimaryDamageDesc", "Primary Damage", "primaryDamage")
        ),
        estimated_retail_value=parse_money(
            first_present(sale_information, "ActualCashValue", "actualCashValue", "ACV", "acv")
            or first_present(attributes, "ActualCashValue", "actualCashValue", "ACV", "acv", "ProviderACV")
        ),
        has_key=parse_boolish(
            first_present(vehicle_information, "Key", "KeySlashFob", "key")
            or first_present(attributes, "Keys", "hasKey", "KeyFOB")
        ),
        drivetrain=normalize_text(
            first_present(vehicle_description, "DriveLineType", "Drive Line Type", "driveTrain", "drivetrain")
            or first_present(attributes, "DriveLineTypeDesc", "Drive Line Type", "driveTrain", "drivetrain")
        ),
        highlights=extract_highlights(attributes, vehicle_information, vehicle_description),
        vin=normalize_text(
            first_present(attributes, "VIN", "VINMask")
            or first_present(vehicle_information, "VIN", "vin", "VINMask")
            or first_present(vehicle_description, "VIN", "vin", "VINMask")
        ),
        status=normalize_status(raw_status),
        sale_date=parse_datetime(
            first_present(sale_information, "AuctionDateTime", "auctionDateTime", "Auction Date and Time", "saleDate")
            or first_present(attributes, "AuctionDateTime", "saleDate")
        ),
        current_bid=parse_money(first_present(sale_information, "CurrentBid", "currentBid", "currentBidAmount")),
        buy_now_price=extract_buy_now_price(
            sale_information,
            bidding_information,
            prebid_information,
            attributes,
            inventory_fields,
        ),
        currency=str(first_present(sale_information, "currency", "currencyCode") or first_present(attributes, "Currency") or "USD"),
        raw_status=raw_status,
        provider_metadata={
            "branch": normalize_text(
                first_present(sale_information, "SellingBranch", "branchName")
                or first_present(attributes, "BranchName", "Name")
            ),
            "item_id": normalize_text(first_present(inventory_fields, "itemId")),
        },
    )


def normalize_status(raw_status: str) -> str:
    normalized = raw_status.strip().lower()
    return STATUS_MAPPING.get(normalized, normalized.replace(" ", "_"))


def derive_raw_status(payload: dict[str, Any]) -> str:
    for field_name in (
        "saleStatus",
        "SaleStatus",
        "auctionStatus",
        "AuctionStatus",
        "bidStatus",
        "BidStatus",
        "status",
        "preBidStatus",
        "PreBidStatus",
    ):
        value = payload.get(field_name)
        normalized = normalize_text(value)
        if normalized:
            return normalized
    sale_date = parse_datetime(first_present(payload, "auctionDateTime", "AuctionDateTime", "saleDate", "SaleDate"))
    if sale_date is None:
        return "upcoming"
    return "live" if sale_date <= datetime.now(timezone.utc) else "upcoming"


def parse_datetime(value: Any) -> Optional[datetime]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    for parser in (
        lambda candidate: datetime.fromisoformat(candidate),
        lambda candidate: datetime.strptime(candidate, "%m/%d/%Y %I:%M:%S %p %z"),
        lambda candidate: datetime.strptime(candidate, "%m/%d/%Y %I:%M:%S %p"),
    ):
        try:
            parsed = parser(text)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def parse_money(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = re.sub(r"[^0-9.\-]", "", str(value))
    if not cleaned:
        return None
    return float(cleaned)


def parse_boolish(value: Any) -> Optional[bool]:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"true", "1", "yes", "y", "available", "present"}:
        return True
    if normalized in {"false", "0", "no", "n", "not available", "missing", "absent"}:
        return False
    return None


def extract_buy_now_price(*containers: dict[str, Any]) -> Optional[float]:
    for container in containers:
        price = parse_money(first_present(container, "buyNowPrice"))
        if price is not None:
            return price
    for container in containers:
        price = parse_money(first_present(container, "buyNowAmount"))
        if price is not None:
            return price
    for container in containers:
        has_buy_now_window = first_present(container, "BuyNowCloseDateTime", "buyNowCloseDateTime")
        price = parse_money(first_present(container, "MinimumBidAmount", "minimumBidAmount"))
        if has_buy_now_window and price is not None:
            return price
    return None


def normalize_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def first_present(payload: dict[str, Any], *field_names: str) -> Any:
    for field_name in field_names:
        for candidate in (field_name, field_name.lower(), canonicalize_field_name(field_name)):
            if candidate in payload and payload[candidate] not in (None, ""):
                return payload[candidate]
    return None


def extract_image_urls(payload: dict[str, Any]) -> list[str]:
    inventory_result = resolve_inventory_result(payload) or {}
    image_information = payload.get("imageInformation") if isinstance(payload.get("imageInformation"), dict) else {}
    inventory_image_information = (
        inventory_result.get("imageInformation") if isinstance(inventory_result.get("imageInformation"), dict) else {}
    )
    image_dimensions = inventory_result.get("imageDimensions") if isinstance(inventory_result.get("imageDimensions"), dict) else {}
    urls = dedupe_urls(
        [
            *extract_image_values(image_information, "StandardImages"),
            *extract_image_values(inventory_image_information, "StandardImages"),
            *extract_image_values(image_information, "ThumbnailImages"),
            *extract_image_values(inventory_image_information, "ThumbnailImages"),
            *extract_dimension_urls(image_dimensions),
        ]
    )
    return urls


def extract_thumbnail_url(payload: dict[str, Any]) -> Optional[str]:
    inventory_result = resolve_inventory_result(payload) or {}
    image_information = payload.get("imageInformation") if isinstance(payload.get("imageInformation"), dict) else {}
    inventory_image_information = (
        inventory_result.get("imageInformation") if isinstance(inventory_result.get("imageInformation"), dict) else {}
    )
    thumbnails = [
        *extract_image_values(image_information, "ThumbnailImages"),
        *extract_image_values(inventory_image_information, "ThumbnailImages"),
    ]
    if thumbnails:
        return thumbnails[0]
    standard_images = [
        *extract_image_values(image_information, "StandardImages"),
        *extract_image_values(inventory_image_information, "StandardImages"),
    ]
    if standard_images:
        return standard_images[0]
    dimension_urls = extract_dimension_urls(
        inventory_result.get("imageDimensions") if isinstance(inventory_result.get("imageDimensions"), dict) else {}
    )
    return dimension_urls[0] if dimension_urls else None


def extract_highlights(*containers: dict[str, Any]) -> list[str]:
    highlights: list[str] = []
    for container in containers:
        for field_name in ("Highlights", "highlights"):
            value = container.get(field_name)
            if isinstance(value, list):
                highlights.extend(normalize_text(item) for item in value if normalize_text(item))
            elif isinstance(value, str):
                highlights.extend(part.strip() for part in value.split(",") if part.strip())
        if parse_boolish(first_present(container, "RunAndDrive", "Run and Drive")) is True:
            highlights.append("Run and Drive")
        if parse_boolish(first_present(container, "Key", "KeySlashFob", "Keys")) is True:
            highlights.append("Key")
    return dedupe_urls(highlights)


def resolve_inventory_result(payload: dict[str, Any]) -> dict[str, Any] | None:
    data_candidate = payload.get("data")
    if isinstance(data_candidate, dict) and looks_like_inventory_result(data_candidate):
        return data_candidate
    return _find_inventory_result(payload, depth=0)


def resolve_auction_information(payload: dict[str, Any]) -> dict[str, Any] | None:
    return _find_auction_information(payload, depth=0)


def looks_like_inventory_result(payload: dict[str, Any]) -> bool:
    if not isinstance(payload, dict):
        return False
    if any(field_name in payload for field_name in ("inventoryId", "itemId", "lotNumber", "Id", "SalvageId")):
        return True
    return any(
        isinstance(payload.get(field_name), (dict, list))
        for field_name in ("vehicleInformation", "saleInformation", "attributes", "imageDimensions")
    )


def _find_inventory_result(payload: dict[str, Any], *, depth: int) -> dict[str, Any] | None:
    if looks_like_inventory_result(payload):
        return payload
    if depth >= 4:
        return None
    for field_name, candidate in payload.items():
        if not isinstance(candidate, dict):
            continue
        if str(field_name).strip().lower() == "inventoryresult":
            return candidate if looks_like_inventory_result(candidate) else _find_inventory_result(candidate, depth=depth + 1)
        resolved = _find_inventory_result(candidate, depth=depth + 1)
        if resolved is not None:
            return resolved
    for candidate in payload.values():
        if not isinstance(candidate, list):
            continue
        for item in candidate:
            if not isinstance(item, dict):
                continue
            resolved = _find_inventory_result(item, depth=depth + 1)
            if resolved is not None:
                return resolved
    return None


def _find_auction_information(payload: dict[str, Any], *, depth: int) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    if looks_like_auction_information(payload):
        return payload
    if depth >= 4:
        return None
    for field_name, candidate in payload.items():
        if not isinstance(candidate, dict):
            continue
        if str(field_name).strip().lower() == "auctioninformation":
            return candidate if looks_like_auction_information(candidate) else _find_auction_information(candidate, depth=depth + 1)
        resolved = _find_auction_information(candidate, depth=depth + 1)
        if resolved is not None:
            return resolved
    return None


def looks_like_auction_information(payload: dict[str, Any]) -> bool:
    if not isinstance(payload, dict):
        return False
    return any(field_name in payload for field_name in ("biddingInformation", "prebidInformation")) and any(
        field_name in payload for field_name in ("stockNumber", "itemID", "itemId")
    )


def build_lot_title(
    vehicle_information: dict[str, Any],
    vehicle_description: dict[str, Any],
    attributes: dict[str, Any],
    inventory_fields: dict[str, Any],
) -> Optional[str]:
    return normalize_text(
        first_present(
            attributes,
            "YearMakeModelSeries",
            "yearMakeModel",
            "description",
            "title",
        )
        or first_present(vehicle_information, "yearMakeModel", "description", "title")
        or first_present(vehicle_description, "YearMakeModelSeries")
        or compose_title_from_parts(attributes, inventory_fields)
    )


def compose_title_from_parts(attributes: dict[str, Any], inventory_fields: dict[str, Any]) -> Optional[str]:
    title_parts = [
        normalize_text(first_present(attributes, "Year") or first_present(inventory_fields, "year")),
        normalize_text(first_present(attributes, "Make") or first_present(inventory_fields, "make")),
        normalize_text(first_present(attributes, "Model") or first_present(inventory_fields, "model")),
        normalize_text(first_present(attributes, "Series") or first_present(inventory_fields, "series")),
    ]
    composed = " ".join(part for part in title_parts if part)
    return composed or None


def flatten_field_map(source: Any) -> dict[str, Any]:
    if isinstance(source, dict):
        mapping: dict[str, Any] = {}
        for field_name, value in source.items():
            register_field_aliases(mapping, field_name, value)
        return mapping
    if isinstance(source, list):
        mapping = {}
        for item in source:
            if not isinstance(item, dict):
                continue
            value = item.get("value")
            for field_name in (item.get("key"), item.get("label"), item.get("name")):
                register_field_aliases(mapping, field_name, value)
        return mapping
    return {}


def merge_field_maps(*mappings: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for mapping in mappings:
        if not mapping:
            continue
        merged.update(mapping)
    return merged


def register_field_aliases(mapping: dict[str, Any], field_name: Any, value: Any) -> None:
    normalized_name = normalize_text(field_name)
    if normalized_name is None:
        return
    for alias in (normalized_name, normalized_name.lower(), canonicalize_field_name(normalized_name)):
        if alias and alias not in mapping:
            mapping[alias] = value


def canonicalize_field_name(field_name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", field_name.lower())


def extract_image_values(container: dict[str, Any], image_set_name: str) -> list[str]:
    images = container.get("images") if isinstance(container.get("images"), dict) else {}
    raw_items = images.get(image_set_name)
    if not isinstance(raw_items, list):
        return []
    values: list[str] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        normalized = normalize_text(item.get("value"))
        if normalized:
            values.append(normalized)
    return values


def extract_dimension_urls(image_dimensions: dict[str, Any]) -> list[str]:
    raw_keys = image_dimensions.get("keys")
    if not isinstance(raw_keys, list):
        return []
    base_url = normalize_text(first_present(image_dimensions, "baseUrl", "imageBaseUrl", "cdnBaseUrl"))
    urls: list[str] = []
    for raw_key in raw_keys:
        normalized_key = normalize_text(raw_key.get("k") if isinstance(raw_key, dict) else raw_key)
        if not normalized_key:
            continue
        if normalized_key.startswith("http://") or normalized_key.startswith("https://"):
            urls.append(normalized_key)
            continue
        if base_url:
            urls.append(f"{base_url.rstrip('/')}/{normalized_key.lstrip('/')}")
            continue
        encoded_key = quote(normalized_key, safe="~")
        urls.append(f"https://vis.iaai.com/resizer?imageKeys={encoded_key}&width=845&height=633")
    return urls


def dedupe_urls(values: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = normalize_text(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped
