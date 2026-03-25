from datetime import datetime, timezone
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2] / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from cartrap.modules.iaai_provider.normalizer import normalize_lot_details_payload, normalize_search_results


def test_normalize_search_results_maps_iaai_fields_into_shared_contract() -> None:
    results = normalize_search_results(
        [
            {
                "id": 99112233,
                "stockNumber": "STK-44",
                "description": "2021 TESLA MODEL 3",
                "auctionDateTime": "2026-03-30T17:00:00Z",
                "vehiclePrimaryImageUrl": "https://img.iaai.com/99112233.jpg",
                "odoValue": "44,210",
                "currency": "USD",
                "branchName": "Phoenix",
                "city": "Phoenix",
                "state": "AZ",
                "market": "US",
                "saleStatus": "Live",
            }
        ]
    )

    assert len(results) == 1
    assert results[0].provider == "iaai"
    assert results[0].provider_lot_id == "99112233"
    assert results[0].lot_number == "STK-44"
    assert results[0].lot_key == "iaai:99112233"
    assert results[0].status == "live"


def test_normalize_lot_details_extracts_images_and_status() -> None:
    snapshot = normalize_lot_details_payload(
        {
            "inventoryResult": {
                "inventoryId": 99112233,
                "vehicleInformation": {
                    "stockNumber": "STK-44",
                    "yearMakeModel": "2021 TESLA MODEL 3",
                    "odometer": "44,210",
                    "vin": "5YJ3E1EA7MF000001",
                },
                "saleInformation": {
                    "auctionDateTime": "2026-03-30T17:00:00Z",
                    "currentBid": 9100,
                    "currency": "USD",
                    "saleStatus": "Sold",
                },
                "attributes": {
                    "Primary Damage": "Front End",
                    "Drive Line Type": "AWD",
                    "Highlights": ["Run and Drive"],
                },
                "imageDimensions": {
                    "baseUrl": "https://img.iaai.com",
                    "keys": ["99112233/1.jpg", "99112233/2.jpg"],
                },
            }
        }
    )

    assert snapshot.provider == "iaai"
    assert snapshot.lot_key == "iaai:99112233"
    assert snapshot.status == "sold"
    assert snapshot.sale_date == datetime(2026, 3, 30, 17, 0, tzinfo=timezone.utc)
    assert [str(url) for url in snapshot.image_urls] == [
        "https://img.iaai.com/99112233/1.jpg",
        "https://img.iaai.com/99112233/2.jpg",
    ]


def test_normalize_lot_details_accepts_direct_inventory_shape_without_inventory_result_wrapper() -> None:
    snapshot = normalize_lot_details_payload(
        {
            "inventoryId": 44610371,
            "vehicleInformation": {
                "stockNumber": "36475260",
                "yearMakeModel": "2014 FORD FOCUS SE",
                "odometer": "124,550",
                "vin": "1FADP3F28EL000001",
            },
            "saleInformation": {
                "auctionDateTime": "2026-03-30T17:00:00Z",
                "currentBid": 650,
                "currency": "USD",
                "saleStatus": "Pre-Bid",
            },
            "attributes": {
                "Primary Damage": "Rear",
                "Highlights": "Run and Drive",
            },
            "imageDimensions": {
                "baseUrl": "https://img.iaai.com",
                "keys": ["44610371/hero.jpg"],
            },
        }
    )

    assert snapshot.provider_lot_id == "44610371"
    assert snapshot.lot_number == "36475260"
    assert snapshot.title == "2014 FORD FOCUS SE"
    assert snapshot.status == "upcoming"
    assert [str(url) for url in snapshot.image_urls] == ["https://img.iaai.com/44610371/hero.jpg"]


def test_normalize_lot_details_accepts_nested_data_wrapper() -> None:
    snapshot = normalize_lot_details_payload(
        {
            "data": {
                "inventoryId": 99112233,
                "vehicleInformation": {
                    "stockNumber": "STK-44",
                    "yearMakeModel": "2021 TESLA MODEL 3",
                },
                "saleInformation": {
                    "saleStatus": "Sold",
                    "currency": "USD",
                },
            }
        }
    )

    assert snapshot.provider_lot_id == "99112233"
    assert snapshot.lot_number == "STK-44"
    assert snapshot.status == "sold"
