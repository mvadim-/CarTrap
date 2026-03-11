"""HTML parsers for Copart lot and search pages."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from bs4 import BeautifulSoup

from cartrap.modules.copart_provider.normalizer import normalize_lot_payload, normalize_search_results


LOT_JSON_PATTERNS = [
    re.compile(r"window\.__lotDetails\s*=\s*(\{.*?\});", re.DOTALL),
    re.compile(r"window\.__INITIAL_LOT_STATE__\s*=\s*(\{.*?\});", re.DOTALL),
]

SEARCH_JSON_PATTERNS = [
    re.compile(r"window\.__searchResults\s*=\s*(\[[\s\S]*?\]);", re.DOTALL),
    re.compile(r"window\.__SEARCH_STATE__\s*=\s*(\{.*?\});", re.DOTALL),
    re.compile(r"window\.__PRELOADED_STATE__\s*=\s*(\{.*?\});", re.DOTALL),
    re.compile(r"window\.__INITIAL_STATE__\s*=\s*(\{.*?\});", re.DOTALL),
]

logger = logging.getLogger(__name__)


class CopartParseError(ValueError):
    """Raised when Copart HTML cannot be parsed into a known payload."""


def parse_lot_page(html: str):
    payload = _extract_lot_payload(html)
    return normalize_lot_payload(payload)


def parse_search_results(html: str):
    payload = _extract_search_payload(html)
    return normalize_search_results(payload)


def _extract_lot_payload(html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")

    json_script = soup.find("script", attrs={"id": "lot-details-data"})
    if json_script and json_script.string:
        data = json.loads(json_script.string)
        if isinstance(data, dict):
            return data

    for pattern in LOT_JSON_PATTERNS:
        match = pattern.search(html)
        if match:
            return json.loads(match.group(1))

    raise CopartParseError("Could not locate lot payload in HTML.")


def _extract_search_payload(html: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")

    for script_id in ("search-results-data", "__NEXT_DATA__", "__NUXT_DATA__"):
        json_script = soup.find("script", attrs={"id": script_id})
        if json_script and json_script.string:
            return _extract_results_from_json(json.loads(json_script.string))

    for pattern in SEARCH_JSON_PATTERNS:
        match = pattern.search(html)
        if match:
            return _extract_results_from_json(json.loads(match.group(1)))

    if _is_challenge_page(html):
        raise CopartParseError("Copart returned an anti-bot challenge page instead of search results.")

    title = soup.title.string.strip() if soup.title and soup.title.string else "unknown"
    script_ids = [script.get("id") for script in soup.find_all("script") if script.get("id")]
    logger.warning("Copart search payload not found. title=%s script_ids=%s", title, script_ids[:10])

    raise CopartParseError("Could not locate search payload in HTML.")


def _ensure_result_list(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise CopartParseError("Search payload is not a list.")
    return [item for item in payload if isinstance(item, dict)]


def _extract_results_from_json(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        if _looks_like_result_list(data):
            return _ensure_result_list(data)
        for item in data:
            try:
                return _extract_results_from_json(item)
            except CopartParseError:
                continue
        raise CopartParseError("Could not locate search payload in JSON list.")

    if isinstance(data, dict):
        direct_results = data.get("results")
        if isinstance(direct_results, list) and _looks_like_result_list(direct_results):
            return _ensure_result_list(direct_results)
        if _looks_like_result_dict(data):
            return [data]
        for value in data.values():
            try:
                return _extract_results_from_json(value)
            except CopartParseError:
                continue
        raise CopartParseError("Could not locate search payload in JSON object.")

    raise CopartParseError("Unsupported search payload type.")


def _looks_like_result_list(value: list[Any]) -> bool:
    if not value:
        return True
    return any(_looks_like_result_dict(item) for item in value if isinstance(item, dict))


def _looks_like_result_dict(value: dict[str, Any]) -> bool:
    keys = set(value.keys())
    return "lotNumber" in keys or {"url", "title"} <= keys


def _is_challenge_page(html: str) -> bool:
    lowered = html.lower()
    challenge_markers = [
        "additional security check is required",
        "imperva",
        "incapsula",
        "captcha",
        "i am human",
        "request unsuccessful",
    ]
    return any(marker in lowered for marker in challenge_markers)
