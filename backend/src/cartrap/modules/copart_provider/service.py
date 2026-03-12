"""Provider facade for Copart JSON API operations."""

from __future__ import annotations

import re
from typing import Optional

from cartrap.modules.copart_provider.client import CopartHttpClient
from cartrap.modules.copart_provider.models import CopartLotSnapshot, CopartSearchResult
from cartrap.modules.copart_provider.normalizer import (
    extract_lot_details,
    extract_search_documents,
    normalize_lot_details_payload,
    normalize_search_results,
)


LOT_NUMBER_PATTERN = re.compile(r"(\d{6,})")


class CopartProvider:
    def __init__(self, client: Optional[CopartHttpClient] = None) -> None:
        self._client = client or CopartHttpClient()

    def fetch_lot(self, lot_reference: str) -> CopartLotSnapshot:
        lot_number = self._extract_lot_number(lot_reference)
        response = self._client.lot_details(lot_number)
        return normalize_lot_details_payload(extract_lot_details(response))

    def search_lots(self, payload: dict) -> list[CopartSearchResult]:
        response = self._client.search(payload)
        return normalize_search_results(extract_search_documents(response))

    def close(self) -> None:
        self._client.close()

    @staticmethod
    def _extract_lot_number(lot_reference: str) -> str:
        match = LOT_NUMBER_PATTERN.search(lot_reference)
        if match is None:
            raise ValueError("Could not determine lot number from reference.")
        return match.group(1)
