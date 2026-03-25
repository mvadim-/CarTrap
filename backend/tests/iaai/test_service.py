from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2] / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from cartrap.modules.iaai_provider.client import IaaiHttpPayloadResponse
from cartrap.modules.iaai_provider.service import IaaiProvider


class FakeIaaiClient:
    def __init__(self, *, lot_payloads: dict[str, dict], search_payload: dict | None = None) -> None:
        self.lot_payloads = lot_payloads
        self.search_payload = search_payload or {"vehicles": []}
        self.requested_inventory_ids: list[str] = []
        self.requested_search_payloads: list[dict] = []

    def lot_details_with_metadata(self, provider_lot_id: str, etag: str | None = None) -> IaaiHttpPayloadResponse:
        del etag
        self.requested_inventory_ids.append(provider_lot_id)
        return IaaiHttpPayloadResponse(payload=self.lot_payloads[provider_lot_id], etag=None, not_modified=False)

    def search(self, payload: dict) -> dict:
        self.requested_search_payloads.append(payload)
        return self.search_payload

    def close(self) -> None:
        return None


def test_fetch_lot_conditional_preserves_inventory_id_market_suffix() -> None:
    client = FakeIaaiClient(
        lot_payloads={
            "45107325~US": {
                "inventoryResult": {
                    "inventoryId": "45107325~US",
                    "vehicleInformation": {"stockNumber": "44610371", "yearMakeModel": "2025 FORD MUSTANG MACH-E"},
                    "saleInformation": {"saleStatus": "Live", "currency": "USD"},
                }
            }
        }
    )

    result = IaaiProvider(client=client).fetch_lot_conditional("45107325~US")

    assert client.requested_inventory_ids == ["45107325~US"]
    assert result.snapshot is not None
    assert result.snapshot.provider_lot_id == "45107325~US"


def test_fetch_lot_conditional_resolves_stock_number_to_inventory_id_before_retrying_lot_details() -> None:
    client = FakeIaaiClient(
        lot_payloads={
            "44610371": {"unexpected": "shape"},
            "45107325~US": {
                "inventoryResult": {
                    "inventoryId": "45107325~US",
                    "vehicleInformation": {
                        "stockNumber": "44610371",
                        "yearMakeModel": "2025 FORD MUSTANG MACH-E",
                    },
                    "saleInformation": {
                        "saleStatus": "Live",
                        "currency": "USD",
                        "auctionDateTime": "2026-03-26T17:00:00Z",
                    },
                }
            },
        },
        search_payload={
            "vehicles": [
                {
                    "id": "45107325~US",
                    "stockNumber": "44610371",
                    "auctionDateTime": "2026-03-26T17:00:00Z",
                }
            ]
        },
    )

    result = IaaiProvider(client=client).fetch_lot_conditional("44610371")

    assert client.requested_inventory_ids == ["44610371", "45107325~US"]
    assert client.requested_search_payloads
    assert client.requested_search_payloads[0]["searches"] == [{"fullSearch": "44610371"}]
    assert result.snapshot is not None
    assert result.snapshot.provider_lot_id == "45107325~US"
    assert result.snapshot.lot_number == "44610371"
    assert result.snapshot.sale_date == datetime(2026, 3, 26, 17, 0, tzinfo=timezone.utc)
