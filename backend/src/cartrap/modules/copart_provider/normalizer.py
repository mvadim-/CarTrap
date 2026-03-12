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
    data_payload = payload.get("data")
    if details is None and isinstance(data_payload, dict):
        details = data_payload.get("lotDetails")
    if not isinstance(details, dict):
        raise ValueError("Copart lot response is missing 'lotDetails' object.")
    merged_details = dict(details)
    if "lotImages" not in merged_details:
        root_images = payload.get("lotImages")
        nested_images = data_payload.get("lotImages") if isinstance(data_payload, dict) else None
        if root_images is not None:
            merged_details["lotImages"] = root_images
        elif nested_images is not None:
            merged_details["lotImages"] = nested_images
    return merged_details


def normalize_lot_payload(payload: dict[str, Any]) -> CopartLotSnapshot:
    raw_status = derive_raw_status(payload)
    lot_number = str(payload["lot_number"])
    return CopartLotSnapshot(
        lot_number=lot_number,
        title=str(payload.get("lot_desc") or payload.get("title") or "Unknown lot"),
        url=build_lot_url(lot_number),
        thumbnail_url=extract_thumbnail_url(payload),
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
    image_urls = extract_image_urls(payload)
    return CopartLotSnapshot(
        lot_number=lot_number,
        title=str(payload.get("lotDescription") or payload.get("title") or "Unknown lot"),
        url=build_lot_url(lot_number),
        thumbnail_url=image_urls[0] if image_urls else extract_thumbnail_url(payload),
        image_urls=image_urls,
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
                thumbnail_url=extract_thumbnail_url(item),
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


def extract_thumbnail_url(payload: dict[str, Any]) -> Optional[str]:
    direct = first_present(
        payload,
        "lot_thumbnail_image_path",
        "thumbnailUrl",
        "thumbnail_url",
        "thumbNail",
        "thumbUrl",
        "imageUrl",
        "image_url",
        "heroImageUrl",
    )
    normalized_direct = normalize_thumbnail_candidate(direct)
    if normalized_direct:
        return normalized_direct

    nested_candidates = [
        payload.get("thumbnail"),
        payload.get("image"),
        payload.get("images"),
        payload.get("imageList"),
        payload.get("timsImages"),
    ]
    for candidate in nested_candidates:
        normalized = normalize_thumbnail_candidate(candidate)
        if normalized:
            return normalized
    return None


def extract_image_urls(payload: dict[str, Any]) -> list[str]:
    urls: list[str] = []
    for candidate in (
        payload.get("lotImages"),
        payload.get("images"),
        payload.get("imageList"),
        payload.get("timsImages"),
    ):
        for url in collect_image_urls(candidate):
            if url not in urls:
                urls.append(url)
    return urls


def collect_image_urls(candidate: Any) -> list[str]:
    if candidate is None or candidate == "":
        return []
    if isinstance(candidate, str):
        normalized = normalize_thumbnail_candidate(candidate)
        return [normalized] if normalized else []
    if isinstance(candidate, list):
        urls: list[str] = []
        for item in candidate:
            for url in collect_image_urls(item):
                if url not in urls:
                    urls.append(url)
        return urls
    if isinstance(candidate, dict):
        direct = normalize_thumbnail_candidate(candidate)
        if direct:
            return [direct]
        urls: list[str] = []
        for value in candidate.values():
            for url in collect_image_urls(value):
                if url not in urls:
                    urls.append(url)
        return urls
    return []


def normalize_thumbnail_candidate(candidate: Any) -> Optional[str]:
    if candidate is None or candidate == "":
        return None
    if isinstance(candidate, str):
        text = candidate.strip()
        if not text:
            return None
        if not looks_like_image_path(text):
            return None
        if "://" not in text and text.startswith("cs.copart.com/"):
            return f"https://{text}"
        if text.startswith("//"):
            return f"https:{text}"
        if text.startswith("/"):
            return f"https://www.copart.com{text}"
        return text
    if isinstance(candidate, list):
        for item in candidate:
            normalized = normalize_thumbnail_candidate(item)
            if normalized:
                return normalized
        return None
    if isinstance(candidate, dict):
        for key in (
            "url",
            "href",
            "thumbnailUrl",
            "thumbnail_url",
            "thumbNail",
            "thumbUrl",
            "imgUrl",
            "imageUrl",
            "image_url",
            "link",
            "full",
        ):
            normalized = normalize_thumbnail_candidate(candidate.get(key))
            if normalized:
                return normalized
    return None


def looks_like_image_path(value: str) -> bool:
    normalized = value.strip().lower()
    return any(
        marker in normalized
        for marker in (
            ".jpg",
            ".jpeg",
            ".png",
            ".webp",
            "img.copart.com/",
            "cs.copart.com/",
            "/content/",
            "/image/",
            "/images/",
            "_thb",
            "_ful",
        )
    )


def build_lot_url(lot_number: str) -> str:
    return f"https://www.copart.com/lot/{lot_number}"


def first_present(payload: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in payload and payload[key] is not None:
            return payload[key]
    return None
