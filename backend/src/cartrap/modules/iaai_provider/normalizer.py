"""Normalization helpers for IAAI mobile payloads."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
import re

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
    vehicles = payload.get("vehicles")
    if not isinstance(vehicles, list):
        raise ValueError("IAAI search payload is missing 'vehicles'.")
    return [item for item in vehicles if isinstance(item, dict)]


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
                title=normalize_text(first_present(item, "description", "itemDescription", "title")) or "Unknown lot",
                url=build_iaai_lot_url(provider_lot_id),
                thumbnail_url=normalize_text(first_present(item, "vehiclePrimaryImageUrl", "thumbnailUrl")),
                location=location or normalize_text(first_present(item, "market")),
                odometer=normalize_text(first_present(item, "odoValue", "odometer")),
                sale_date=parse_datetime(first_present(item, "auctionDateTime", "saleDate")),
                current_bid=parse_money(first_present(item, "currentBidAmount", "currentBid")),
                buy_now_price=parse_money(first_present(item, "buyNowAmount", "buyNowPrice")),
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


def normalize_lot_details_payload(payload: dict[str, Any]) -> AuctionLotSnapshot:
    inventory_result = payload.get("inventoryResult")
    if not isinstance(inventory_result, dict):
        raise ValueError("IAAI lot payload is missing 'inventoryResult'.")
    sale_information = inventory_result.get("saleInformation") if isinstance(inventory_result.get("saleInformation"), dict) else {}
    vehicle_information = (
        inventory_result.get("vehicleInformation") if isinstance(inventory_result.get("vehicleInformation"), dict) else {}
    )
    attributes = inventory_result.get("attributes") if isinstance(inventory_result.get("attributes"), dict) else {}
    provider_lot_id = str(first_present(inventory_result, "inventoryId", "id", "itemId"))
    lot_number = str(
        first_present(vehicle_information, "stockNumber", "itemId", "lotNumber")
        or first_present(inventory_result, "stockNumber", "itemId", "lotNumber")
    )
    raw_status = derive_raw_status(
        {
            **inventory_result,
            **sale_information,
            **vehicle_information,
            **attributes,
        }
    )
    image_urls = extract_image_urls(payload)
    return AuctionLotSnapshot(
        provider=PROVIDER_IAAI,
        auction_label=get_auction_label(PROVIDER_IAAI),
        provider_lot_id=provider_lot_id,
        lot_number=lot_number,
        title=normalize_text(first_present(vehicle_information, "yearMakeModel", "description", "title")) or "Unknown lot",
        url=build_iaai_lot_url(provider_lot_id),
        thumbnail_url=image_urls[0] if image_urls else normalize_text(first_present(payload, "vehiclePrimaryImageUrl")),
        image_urls=image_urls,
        odometer=normalize_text(first_present(vehicle_information, "odometer", "odoValue")),
        primary_damage=normalize_text(first_present(attributes, "Primary Damage", "primaryDamage")),
        estimated_retail_value=parse_money(first_present(attributes, "Actual Cash Value", "actualCashValue", "acv")),
        has_key=parse_boolish(first_present(attributes, "Keys", "hasKey")),
        drivetrain=normalize_text(first_present(attributes, "Drive Line Type", "driveTrain", "drivetrain")),
        highlights=extract_highlights(attributes),
        vin=normalize_text(first_present(vehicle_information, "vin", "VIN")),
        status=normalize_status(raw_status),
        sale_date=parse_datetime(first_present(sale_information, "auctionDateTime", "saleDate")),
        current_bid=parse_money(first_present(sale_information, "currentBid", "currentBidAmount")),
        buy_now_price=parse_money(first_present(sale_information, "buyNowAmount", "buyNowPrice")),
        currency=str(first_present(sale_information, "currency", "currencyCode") or "USD"),
        raw_status=raw_status,
        provider_metadata={
            "branch": normalize_text(first_present(sale_information, "branchName")),
            "item_id": normalize_text(first_present(inventory_result, "itemId")),
        },
    )


def normalize_status(raw_status: str) -> str:
    normalized = raw_status.strip().lower()
    return STATUS_MAPPING.get(normalized, normalized.replace(" ", "_"))


def derive_raw_status(payload: dict[str, Any]) -> str:
    for field_name in (
        "saleStatus",
        "auctionStatus",
        "bidStatus",
        "status",
        "preBidStatus",
    ):
        value = payload.get(field_name)
        normalized = normalize_text(value)
        if normalized:
            return normalized
    sale_date = parse_datetime(first_present(payload, "auctionDateTime", "saleDate"))
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
    parsed = datetime.fromisoformat(text)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


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
    if normalized in {"true", "1", "yes", "y", "available"}:
        return True
    if normalized in {"false", "0", "no", "n", "not available"}:
        return False
    return None


def normalize_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def first_present(payload: dict[str, Any], *field_names: str) -> Any:
    for field_name in field_names:
        if field_name in payload and payload[field_name] not in (None, ""):
            return payload[field_name]
    return None


def extract_image_urls(payload: dict[str, Any]) -> list[str]:
    inventory_result = payload.get("inventoryResult") if isinstance(payload.get("inventoryResult"), dict) else {}
    image_dimensions = inventory_result.get("imageDimensions") if isinstance(inventory_result.get("imageDimensions"), dict) else {}
    raw_keys = image_dimensions.get("keys")
    if not isinstance(raw_keys, list):
        return []
    base_url = normalize_text(
        first_present(
            image_dimensions,
            "baseUrl",
            "imageBaseUrl",
            "cdnBaseUrl",
        )
    )
    urls: list[str] = []
    for key in raw_keys:
        normalized_key = normalize_text(key)
        if not normalized_key:
            continue
        if normalized_key.startswith("http://") or normalized_key.startswith("https://"):
            urls.append(normalized_key)
            continue
        if base_url:
            urls.append(f"{base_url.rstrip('/')}/{normalized_key.lstrip('/')}")
    return urls


def extract_highlights(attributes: dict[str, Any]) -> list[str]:
    highlights: list[str] = []
    for field_name in ("Highlights", "highlights"):
        value = attributes.get(field_name)
        if isinstance(value, list):
            highlights.extend(normalize_text(item) for item in value if normalize_text(item))
        elif isinstance(value, str):
            highlights.extend(part.strip() for part in value.split(",") if part.strip())
    return highlights
