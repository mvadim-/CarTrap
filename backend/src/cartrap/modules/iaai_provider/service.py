"""Provider facade for IAAI mobile API operations."""

from __future__ import annotations

from datetime import datetime, timezone
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


IAAI_REFERENCE_PATTERN = re.compile(r"(\d{4,}(?:~[A-Za-z]{2,})?)")


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
        try:
            snapshot = normalize_lot_details_payload(response.payload)
        except ValueError as exc:
            resolved_inventory_id = self._resolve_inventory_id_from_stock_number(
                lot_reference=lot_reference,
                attempted_inventory_id=inventory_id,
                payload_error=exc,
            )
            if not resolved_inventory_id or resolved_inventory_id == inventory_id:
                raise
            response = self._client.lot_details_with_metadata(resolved_inventory_id, etag=etag)
            if response.not_modified:
                return IaaiLotFetchResult(snapshot=None, etag=response.etag, not_modified=True)
            if response.payload is None:
                raise RuntimeError("IAAI lot-details payload is missing after stock-number lookup.")
            snapshot = normalize_lot_details_payload(response.payload)
        return IaaiLotFetchResult(
            snapshot=snapshot,
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

    def _resolve_inventory_id_from_stock_number(
        self,
        *,
        lot_reference: str,
        attempted_inventory_id: str,
        payload_error: ValueError,
    ) -> str | None:
        if "inventoryResult" not in str(payload_error):
            return None
        if "~" in attempted_inventory_id:
            return None
        stock_number = self._extract_stock_number(lot_reference)
        if stock_number is None:
            return None
        response = self._client.search(self._build_stock_number_lookup_payload(stock_number))
        for vehicle in extract_search_vehicles(response):
            candidate_stock_number = str(vehicle.get("stockNumber") or "").strip()
            candidate_inventory_id = str(vehicle.get("id") or vehicle.get("inventoryId") or "").strip()
            if candidate_stock_number == stock_number and candidate_inventory_id:
                return candidate_inventory_id
        return None

    @staticmethod
    def _extract_inventory_id(lot_reference: str) -> str:
        match = IAAI_REFERENCE_PATTERN.search(str(lot_reference))
        if match is None:
            raise ValueError("Could not determine IAAI inventory id from reference.")
        return match.group(1)

    @staticmethod
    def _extract_stock_number(lot_reference: str) -> str | None:
        match = re.search(r"(\d{4,})", str(lot_reference))
        return match.group(1) if match else None

    @staticmethod
    def _build_stock_number_lookup_payload(stock_number: str) -> dict:
        timestamp = datetime.now(timezone.utc).strftime("%m/%d/%Y %I:%M:%S %p")
        return {
            "returnFacets": False,
            "generateFacets": False,
            "zipCode": "",
            "pageSize": 25,
            "ShowRecommendations": False,
            "miles": 0,
            "useFastDistance": False,
            "sort": [{"isDescending": False, "isGeoSort": False, "sortField": "AuctionDateTime"}],
            "clientDateTimeInUtc": timestamp,
            "currentPage": 1,
            "returnAllIDs": False,
            "point": {"latitude": 0, "longitude": 0},
            "skipCaching": False,
            "roughGeoSearch": False,
            "includeReasoning": False,
            "IsSearchTimedAuction": False,
            "searches": [{"fullSearch": stock_number}],
            "includeLikeWords": True,
            "created": timestamp,
        }
