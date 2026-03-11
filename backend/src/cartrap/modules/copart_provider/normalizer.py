"""Normalization helpers for Copart raw payloads."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from cartrap.modules.copart_provider.models import CopartLotSnapshot, CopartSearchResult


STATUS_MAPPING = {
    "on approval": "on_approval",
    "pure sale": "pure_sale",
    "minimum bid": "minimum_bid",
    "sold": "sold",
    "live": "live",
    "upcoming": "upcoming",
}


def normalize_lot_payload(payload: dict[str, Any]) -> CopartLotSnapshot:
    raw_status = str(payload.get("status") or payload.get("saleStatus") or "upcoming")
    return CopartLotSnapshot(
        lot_number=str(payload["lotNumber"]),
        title=str(payload.get("title") or payload.get("description") or "Unknown lot"),
        url=str(payload["url"]),
        status=normalize_status(raw_status),
        sale_date=parse_datetime(payload.get("saleDate")),
        current_bid=parse_money(payload.get("currentBid")),
        buy_now_price=parse_money(payload.get("buyItNowPrice")),
        currency=str(payload.get("currency") or "USD"),
        raw_status=raw_status,
    )


def normalize_search_results(payload: list[dict[str, Any]]) -> list[CopartSearchResult]:
    results: list[CopartSearchResult] = []
    for item in payload:
        raw_status = str(item.get("status") or item.get("saleStatus") or "upcoming")
        results.append(
            CopartSearchResult(
                lot_number=str(item["lotNumber"]),
                title=str(item.get("title") or item.get("description") or "Unknown lot"),
                url=str(item["url"]),
                location=item.get("location"),
                sale_date=parse_datetime(item.get("saleDate")),
                current_bid=parse_money(item.get("currentBid")),
                currency=str(item.get("currency") or "USD"),
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
