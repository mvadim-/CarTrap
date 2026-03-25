"""Provider facade for IAAI mobile API operations."""

from __future__ import annotations

import re
from typing import Optional

from cartrap.modules.iaai_provider.client import IaaiHttpClient
from cartrap.modules.iaai_provider.models import IaaiLotFetchResult, IaaiSearchCountFetchResult, IaaiSearchPage
from cartrap.modules.iaai_provider.normalizer import (
    extract_search_total,
    extract_search_vehicles,
    normalize_lot_details_payload,
    normalize_search_results,
)


IAAI_REFERENCE_PATTERN = re.compile(r"(\d{4,})")


class IaaiProvider:
    def __init__(self, client: Optional[IaaiHttpClient] = None) -> None:
        self._client = client or IaaiHttpClient()

    def fetch_lot(self, lot_reference: str):
        result = self.fetch_lot_conditional(lot_reference)
        if result.not_modified or result.snapshot is None:
            raise RuntimeError("IAAI lot snapshot is not available for a 304 response.")
        return result.snapshot

    def fetch_lot_conditional(self, lot_reference: str, etag: Optional[str] = None) -> IaaiLotFetchResult:
        inventory_id = self._extract_inventory_id(lot_reference)
        response = self._client.lot_details_with_metadata(inventory_id, etag=etag)
        if response.not_modified:
            return IaaiLotFetchResult(snapshot=None, etag=response.etag, not_modified=True)
        if response.payload is None:
            raise RuntimeError("IAAI lot-details payload is missing.")
        return IaaiLotFetchResult(
            snapshot=normalize_lot_details_payload(response.payload),
            etag=response.etag,
            not_modified=False,
        )

    def search_lots(self, payload: dict) -> IaaiSearchPage:
        response = self._client.search(payload)
        return IaaiSearchPage(
            results=normalize_search_results(extract_search_vehicles(response)),
            num_found=extract_search_total(response),
        )

    def fetch_search_count_conditional(self, payload: dict, etag: Optional[str] = None) -> IaaiSearchCountFetchResult:
        response = self._client.search_with_metadata(payload, etag=etag)
        if response.not_modified:
            return IaaiSearchCountFetchResult(num_found=None, etag=response.etag, not_modified=True)
        if response.payload is None:
            raise RuntimeError("IAAI search payload is missing.")
        return IaaiSearchCountFetchResult(
            num_found=extract_search_total(response.payload),
            etag=response.etag,
            not_modified=False,
        )

    def close(self) -> None:
        self._client.close()

    @staticmethod
    def _extract_inventory_id(lot_reference: str) -> str:
        match = IAAI_REFERENCE_PATTERN.search(str(lot_reference))
        if match is None:
            raise ValueError("Could not determine IAAI inventory id from reference.")
        return match.group(1)
