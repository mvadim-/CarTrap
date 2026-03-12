"""Catalog refresh helpers for Copart make/model metadata."""

from __future__ import annotations

import concurrent.futures
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from json import JSONDecodeError
from pathlib import Path
from typing import Any, Callable, Optional

from cartrap.modules.copart_provider.service import CopartProvider
from cartrap.modules.search.catalog_builder import build_catalog, build_official_model_index, extract_catalog_candidates


VPIC_ENDPOINT = "https://vpic.nhtsa.dot.gov/api/vehicles/GetModelsForMake/{make}?format=json"


def fetch_models_for_make(make_name: str, retries: int = 3) -> list[str]:
    encoded_make = urllib.parse.quote(make_name)
    url = VPIC_ENDPOINT.format(make=encoded_make)
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=20) as response:
                payload = json.load(response)
            results = payload.get("Results") or []
            return sorted({str(item.get("Model_Name")).strip() for item in results if item.get("Model_Name")})
        except (OSError, ValueError, JSONDecodeError):
            if attempt == retries - 1:
                raise
            time.sleep(0.5 * (attempt + 1))
    return []


def generate_catalog_from_keyword_payload(
    keyword_payload: dict[str, dict[str, Any]],
    source_keywords_path: str,
    manual_overrides: Optional[dict[str, str]] = None,
    model_fetcher: Callable[[str], list[str]] = fetch_models_for_make,
    max_workers: int = 4,
) -> dict[str, Any]:
    candidates = extract_catalog_candidates(keyword_payload)
    make_names = {make["slug"]: make["name"] for make in candidates["makes"]}
    models_by_make: dict[str, list[str]] = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {
            executor.submit(model_fetcher, make["name"]): make
            for make in candidates["makes"]
        }
        for future in concurrent.futures.as_completed(future_map):
            make = future_map[future]
            try:
                models_by_make[make["slug"]] = future.result()
            except Exception:
                models_by_make[make["slug"]] = []

    official_index = build_official_model_index(models_by_make, make_names)
    catalog = build_catalog(
        candidates,
        official_index,
        source_keywords_path,
        manual_overrides=manual_overrides or {},
    )
    catalog["generated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return catalog


class SearchCatalogRefreshJob:
    def __init__(
        self,
        provider_factory: Optional[Callable[[], CopartProvider]] = None,
        overrides_path: Optional[Path] = None,
        model_fetcher: Callable[[str], list[str]] = fetch_models_for_make,
    ) -> None:
        self._provider_factory = provider_factory or CopartProvider
        self._overrides_path = overrides_path
        self._model_fetcher = model_fetcher

    def refresh(self) -> dict[str, Any]:
        provider = self._provider_factory()
        try:
            keyword_payload = provider.fetch_search_keywords()
        finally:
            provider.close()
        manual_overrides = self._load_manual_overrides()
        catalog = generate_catalog_from_keyword_payload(
            keyword_payload,
            "copart_api:/mcs/v2/public/data/search/keywords",
            manual_overrides=manual_overrides,
            model_fetcher=self._model_fetcher,
        )
        if self._overrides_path is not None:
            catalog["manual_overrides_path"] = str(self._overrides_path)
            catalog["manual_override_count"] = len(manual_overrides)
        return catalog

    def _load_manual_overrides(self) -> dict[str, str]:
        if self._overrides_path is None or not self._overrides_path.exists():
            return {}
        payload = json.loads(self._overrides_path.read_text())
        return {str(key): str(value) for key, value in payload.items()}
