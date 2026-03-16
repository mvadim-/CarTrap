"""Provider facade for Copart JSON API operations."""

from __future__ import annotations

import re
from typing import Optional

from cartrap.modules.copart_provider.client import CopartHttpClient
from cartrap.modules.copart_provider.models import (
    CopartLotFetchResult,
    CopartLotSnapshot,
    CopartSearchCountFetchResult,
    CopartSearchPage,
)
from cartrap.modules.copart_provider.normalizer import (
    extract_lot_details,
    extract_search_documents,
    extract_search_num_found,
    normalize_lot_details_payload,
    normalize_search_results,
)


LOT_NUMBER_PATTERN = re.compile(r"(\d{6,})")


class CopartProvider:
    def __init__(self, client: Optional[CopartHttpClient] = None) -> None:
        self._client = client or CopartHttpClient()

    def fetch_lot(self, lot_reference: str) -> CopartLotSnapshot:
        result = self.fetch_lot_conditional(lot_reference)
        if result.not_modified or result.snapshot is None:
            raise RuntimeError("Lot snapshot is not available for a 304 response.")
        return result.snapshot

    def fetch_lot_conditional(self, lot_reference: str, etag: Optional[str] = None) -> CopartLotFetchResult:
        lot_number = self._extract_lot_number(lot_reference)
        response = self._client.lot_details_with_metadata(lot_number, etag=etag)
        if response.not_modified:
            return CopartLotFetchResult(snapshot=None, etag=response.etag, not_modified=True)
        return CopartLotFetchResult(
            snapshot=normalize_lot_details_payload(extract_lot_details(response.payload)),
            etag=response.etag,
            not_modified=False,
        )

    def search_lots(self, payload: dict) -> CopartSearchPage:
        response = self._client.search(payload)
        return CopartSearchPage(
            results=normalize_search_results(extract_search_documents(response)),
            num_found=extract_search_num_found(response),
        )

    def fetch_search_count_conditional(self, payload: dict, etag: Optional[str] = None) -> CopartSearchCountFetchResult:
        response = self._client.search_count_with_metadata(payload, etag=etag)
        if response.not_modified:
            return CopartSearchCountFetchResult(num_found=None, etag=response.etag, not_modified=True)
        return CopartSearchCountFetchResult(
            num_found=extract_search_num_found(response.payload),
            etag=response.etag,
            not_modified=False,
        )

    def fetch_search_keywords(self) -> dict:
        return self._client.search_keywords()

    def close(self) -> None:
        self._client.close()

    @staticmethod
    def _extract_lot_number(lot_reference: str) -> str:
        match = LOT_NUMBER_PATTERN.search(lot_reference)
        if match is None:
            raise ValueError("Could not determine lot number from reference.")
        return match.group(1)
