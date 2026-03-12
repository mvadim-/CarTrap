"""Normalization helpers for Copart API payloads."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from cartrap.modules.copart_provider.models import CopartLotSnapshot, CopartSearchResult


STATUS_MAPPING = {
    "on approval": "on_approval",
    "pure sale": "pure_sale",
    "puresale": "pure_sale",
    "minimum bid": "minimum_bid",
    "sold": "sold",
    "live": "live",
    "upcoming": "upcoming",
}


def extract_search_documents(payload: dict[str, Any]) -> list[dict[str, Any]]:
    response = payload.get("response")
    if not isinstance(response, dict):
        raise ValueError("Copart response is missing 'response' object.")
    documents = response.get("docs")
    if not isinstance(documents, list):
        raise ValueError("Copart response is missing 'docs' list.")
    return [item for item in documents if isinstance(item, dict)]


def extract_lot_details(payload: dict[str, Any]) -> dict[str, Any]:
    details = payload.get("lotDetails")
    if not isinstance(details, dict):
        raise ValueError("Copart lot response is missing 'lotDetails' object.")
    return details


def normalize_lot_payload(payload: dict[str, Any]) -> CopartLotSnapshot:
    raw_status = derive_raw_status(payload)
    lot_number = str(payload["lot_number"])
    return CopartLotSnapshot(
        lot_number=lot_number,
        title=str(payload.get("lot_desc") or payload.get("title") or "Unknown lot"),
        url=build_lot_url(lot_number),
        status=normalize_status(raw_status),
        sale_date=parse_datetime(first_present(payload, "auction_date_utc", "saleDate")),
        current_bid=parse_money(first_present(payload, "current_high_bid", "currentBid")),
        buy_now_price=parse_money(first_present(payload, "buy_it_now_price", "buyItNowPrice")),
        currency=str(first_present(payload, "currency_code", "currency") or "USD"),
        raw_status=raw_status,
    )


def normalize_lot_details_payload(payload: dict[str, Any]) -> CopartLotSnapshot:
    raw_status = derive_raw_status(payload)
    lot_number = str(payload["lotNumber"])
    return CopartLotSnapshot(
        lot_number=lot_number,
        title=str(payload.get("lotDescription") or payload.get("title") or "Unknown lot"),
        url=build_lot_url(lot_number),
        status=normalize_status(raw_status),
        sale_date=parse_datetime(first_present(payload, "saleDate", "auction_date_utc")),
        current_bid=parse_money(first_present(payload, "currentBid", "displayBidAmount")),
        buy_now_price=parse_money(first_present(payload, "buyTodayBid", "buy_it_now_price", "buyItNowPrice")),
        currency=str(first_present(payload, "currencyCode", "currency_code", "currency") or "USD"),
        raw_status=raw_status,
    )


def normalize_search_results(payload: list[dict[str, Any]]) -> list[CopartSearchResult]:
    results: list[CopartSearchResult] = []
    for item in payload:
        raw_status = derive_raw_status(item)
        lot_number = str(item["lot_number"])
        results.append(
            CopartSearchResult(
                lot_number=lot_number,
                title=str(item.get("lot_desc") or item.get("title") or "Unknown lot"),
                url=build_lot_url(lot_number),
                location=str(item.get("yard_name") or item.get("auction_host_name") or "Unknown location"),
                sale_date=parse_datetime(first_present(item, "auction_date_utc", "saleDate")),
                current_bid=parse_money(first_present(item, "current_high_bid", "currentBid")),
                currency=str(first_present(item, "currency_code", "currency") or "USD"),
                status=normalize_status(raw_status),
            )
        )
    return results


def normalize_status(raw_status: str) -> str:
    normalized = raw_status.strip().lower()
    return STATUS_MAPPING.get(normalized, normalized.replace(" ", "_"))


def parse_money(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = str(value).replace("$", "").replace(",", "").strip()
    return float(cleaned)


def parse_datetime(value: Any) -> Optional[datetime]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).strip()
    if text.endswith("Z"):
        text = text.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def derive_raw_status(payload: dict[str, Any]) -> str:
    explicit_status = payload.get("status") or payload.get("saleStatus")
    if explicit_status:
        return str(explicit_status)
    sale_date = parse_datetime(first_present(payload, "auction_date_utc", "saleDate"))
    if sale_date is None:
        return "upcoming"
    return "live" if sale_date <= datetime.now(timezone.utc) else "upcoming"


def build_lot_url(lot_number: str) -> str:
    return f"https://www.copart.com/lot/{lot_number}"


def first_present(payload: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in payload and payload[key] is not None:
            return payload[key]
    return None
