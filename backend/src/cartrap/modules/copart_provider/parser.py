"""HTML parsers for Copart lot and search pages."""

from __future__ import annotations

import json
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
]


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

    json_script = soup.find("script", attrs={"id": "search-results-data"})
    if json_script and json_script.string:
        data = json.loads(json_script.string)
        if isinstance(data, dict):
            results = data.get("results", [])
        else:
            results = data
        return _ensure_result_list(results)

    for pattern in SEARCH_JSON_PATTERNS:
        match = pattern.search(html)
        if match:
            data = json.loads(match.group(1))
            if isinstance(data, dict):
                return _ensure_result_list(data.get("results", []))
            return _ensure_result_list(data)

    raise CopartParseError("Could not locate search payload in HTML.")


def _ensure_result_list(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise CopartParseError("Search payload is not a list.")
    return [item for item in payload if isinstance(item, dict)]
