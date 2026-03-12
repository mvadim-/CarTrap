"""Provider facade for Copart JSON API operations."""

from __future__ import annotations

import re
from typing import Optional

from cartrap.modules.copart_provider.client import CopartHttpClient
from cartrap.modules.copart_provider.models import CopartApiSearchRequest, CopartLotSnapshot, CopartSearchResult
from cartrap.modules.copart_provider.normalizer import extract_search_documents, normalize_lot_payload, normalize_search_results


LOT_NUMBER_PATTERN = re.compile(r"(\d{6,})")


class CopartProvider:
    def __init__(self, client: Optional[CopartHttpClient] = None) -> None:
        self._client = client or CopartHttpClient()

    def fetch_lot(self, lot_reference: str) -> CopartLotSnapshot:
        lot_number = self._extract_lot_number(lot_reference)
        response = self._client.search(self._build_lot_lookup_request(lot_number).to_payload())
        documents = extract_search_documents(response)
        for document in documents:
            if str(document.get("lot_number")) == lot_number:
                return normalize_lot_payload(document)
        raise ValueError(f"Lot {lot_number} was not found in Copart API response.")

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

    @staticmethod
    def _build_lot_lookup_request(lot_number: str) -> CopartApiSearchRequest:
        return CopartApiSearchRequest(
            misc=[f"lot_number:{lot_number}"],
            sort=["auction_date_type desc", "auction_date_utc asc"],
            filter=[],
            local_filters=[],
            latlng_facets=False,
            page_number=1,
            user_start_utc_datetime="1970-01-01T00:00:00Z",
        )
