from datetime import datetime, timezone
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2] / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from cartrap.modules.iaai_provider.normalizer import (
    extract_search_vehicles,
    normalize_lot_details_payload,
    normalize_search_results,
)


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


def test_normalize_search_results_prefers_vehicle_identity_title_over_sale_document() -> None:
    payload = {
        "totalCount": 1,
        "results": [
            {
                "data": {
                    "id": "45107325~US",
                    "itemId": "62993275",
                    "stockNumber": "44610371",
                    "year": "2025",
                    "make": "FORD",
                    "model": "MUSTANG MACH-E",
                    "series": "GT",
                    "title": "CLEAR-PA",
                    "saleDocument": "Clear",
                    "auctionDateTime": "2026-03-26T17:00:00+00:00",
                    "vehiclePrimaryImageUrl": "https://vis.iaai.com/resizer?imageKeys=45107325~SID~I1&width=400&height=300",
                    "odoValue": "2728",
                    "currency": "USD",
                    "branchName": "Electric Vehicle Auctions",
                    "city": "Rancho Cordova",
                    "state": "CA",
                    "market": "IAA United States",
                }
            }
        ],
    }

    results = normalize_search_results(extract_search_vehicles(payload))

    assert len(results) == 1
    assert results[0].provider_lot_id == "45107325~US"
    assert results[0].lot_number == "44610371"
    assert results[0].title == "2025 FORD MUSTANG MACH-E GT"
    assert results[0].lot_key == "iaai:45107325~US"


def test_normalize_search_results_prefers_buy_now_price_over_zero_amount() -> None:
    results = normalize_search_results(
        [
            {
                "id": "55112233~US",
                "stockNumber": "STK-55",
                "description": "2024 HYUNDAI IONIQ 5",
                "auctionDateTime": "2026-03-30T17:00:00Z",
                "buyNowAmount": 0,
                "buyNowPrice": "$19,750",
                "currency": "USD",
                "saleStatus": "Pre-Bid",
            }
        ]
    )

    assert len(results) == 1
    assert results[0].buy_now_price == 19750.0


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


def test_normalize_lot_details_prefers_buy_now_price_from_bidding_payload() -> None:
    snapshot = normalize_lot_details_payload(
        {
            "inventoryResult": {
                "inventoryId": "62993275",
                "vehicleInformation": {
                    "stockNumber": "44610371",
                    "yearMakeModel": "2025 FORD MUSTANG MACH-E GT",
                },
                "saleInformation": {
                    "auctionDateTime": "2026-03-26T17:00:00Z",
                    "currentBid": 9100,
                    "currency": "USD",
                    "saleStatus": "Pre-Bid",
                },
                "biddingInformation": {
                    "buyNowAmount": 0.0,
                    "buyNowPrice": "$18,400",
                },
                "prebidInformation": {
                    "buyNowPrice": "$18,400",
                },
            }
        }
    )

    assert snapshot.provider_lot_id == "62993275"
    assert snapshot.lot_number == "44610371"
    assert snapshot.buy_now_price == 18400.0


def test_normalize_lot_details_reads_buy_now_from_sibling_auction_information() -> None:
    snapshot = normalize_lot_details_payload(
        {
            "auctionInformation": {
                "itemID": "63189723",
                "stockNumber": "44610371",
                "currencyInd": "USD",
                "biddingInformation": {
                    "buyNowAmount": 19250,
                    "buyNowPrice": "$19,250",
                },
                "prebidInformation": {
                    "buyNowPrice": "$19,250",
                },
                "saleInformation": {
                    "date": "3/26/2026 5:00:00 PM +00:00",
                },
            },
            "data": {
                "id": "45107325~US",
                "itemId": "63189723",
                "stockNumber": "44610371",
                "year": "2025",
                "make": "FORD",
                "model": "MUSTANG MACH-E",
                "series": "GT",
                "auctionDateTime": "2026-03-26T17:00:00+00:00",
                "currency": "USD",
            },
        }
    )

    assert snapshot.provider_lot_id == "45107325~US"
    assert snapshot.lot_number == "44610371"
    assert snapshot.title == "2025 FORD MUSTANG MACH-E GT"
    assert snapshot.buy_now_price == 19250.0


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


def test_normalize_lot_details_accepts_capitalized_and_deeply_nested_wrappers() -> None:
    snapshot = normalize_lot_details_payload(
        {
            "Data": {
                "InventoryDetails": {
                    "Result": {
                        "inventoryId": 11223344,
                        "vehicleInformation": {
                            "stockNumber": "IAAI-55",
                            "yearMakeModel": "2020 CHEVROLET BOLT EV",
                        },
                        "saleInformation": {
                            "saleStatus": "Live",
                            "currency": "USD",
                        },
                    }
                }
            }
        }
    )

    assert snapshot.provider_lot_id == "11223344"
    assert snapshot.lot_number == "IAAI-55"
    assert snapshot.status == "live"


def test_normalize_lot_details_maps_real_trace_shape_from_login_flow_dump() -> None:
    snapshot = normalize_lot_details_payload(
        {
            "inventoryResult": {
                "attributes": {
                    "Id": "44981230~US",
                    "SalvageId": "44981230",
                    "StockNumber": "44484523",
                    "Year": "2025",
                    "Make": "FORD",
                    "Model": "MUSTANG MACH-E",
                    "Series": "GT",
                    "YearMakeModelSeries": "2025 FORD MUSTANG MACH-E GT",
                    "PrimaryDamageDesc": "RIGHT FRONT",
                    "Keys": "True",
                    "ODOValue": "5568",
                    "VIN": "3FMTK4SX8SMA28701",
                    "VINMask": "3FMTK4SX8SM******",
                    "DriveLineTypeDesc": "AWD",
                    "AuctionDateTime": "3/26/2026 5:00:00 PM +00:00",
                    "Currency": "USD",
                    "BranchName": "Electric Vehicle Auctions",
                },
                "itemId": "62724767",
                "vehicleInformation": [
                    {"key": "StockHash", "value": "44484523", "label": "Stock #"},
                    {"key": "PrimaryDamage", "value": "Right Front", "label": "Primary Damage"},
                    {"key": "KeySlashFob", "value": "Present", "label": "Key"},
                    {"key": "Odometer", "value": "5,568 mi (Actual)", "label": "Odometer"},
                    {"key": "VINMask", "value": "3FMTK4SX8SM****** (OK)", "label": "VIN Status"},
                ],
                "vehicleDescription": [
                    {"key": "DriveLineType", "value": "All Wheel Drive", "label": "Drive Line Type"},
                    {"key": "Model", "value": "MUSTANG MACH-E", "label": "Model"},
                    {"key": "Series", "value": "GT", "label": "Series"},
                ],
                "saleInformation": [
                    {"key": "SellingBranch", "value": "Electric Vehicle Auctions", "label": "Selling Branch"},
                    {"key": "AuctionDateTime", "value": "3/26/2026 5:00:00 PM +00:00", "label": "Auction Date and Time"},
                    {"key": "ActualCashValue", "value": "$42,689 USD", "label": "Actual Cash Value"},
                ],
                "imageDimensions": {
                    "keys": [
                        {"k": "44981230~SID~B749~S0~I1~RW2576~H1932~TH0"},
                    ]
                },
            },
            "imageInformation": {
                "images": {
                    "StandardImages": [
                        {
                            "key": "1",
                            "value": "https://vis.iaai.com/resizer?imageKeys=44981230~SID~B749~S0~I1~RW2576~H1932~TH0&width=845&height=633",
                        }
                    ],
                    "ThumbnailImages": [
                        {
                            "key": "1",
                            "value": "https://vis.iaai.com/resizer?imageKeys=44981230~SID~B749~S0~I1~RW2576~H1932~TH0&width=400&height=300",
                        }
                    ],
                }
            },
        }
    )

    assert snapshot.provider_lot_id == "44981230~US"
    assert snapshot.lot_number == "44484523"
    assert snapshot.title == "2025 FORD MUSTANG MACH-E GT"
    assert str(snapshot.thumbnail_url) == "https://vis.iaai.com/resizer?imageKeys=44981230~SID~B749~S0~I1~RW2576~H1932~TH0&width=400&height=300"
    assert [str(url) for url in snapshot.image_urls] == [
        "https://vis.iaai.com/resizer?imageKeys=44981230~SID~B749~S0~I1~RW2576~H1932~TH0&width=845&height=633",
        "https://vis.iaai.com/resizer?imageKeys=44981230~SID~B749~S0~I1~RW2576~H1932~TH0&width=400&height=300",
    ]
    assert snapshot.odometer == "5,568 mi (Actual)"
    assert snapshot.primary_damage == "Right Front"
    assert snapshot.estimated_retail_value == 42689.0
    assert snapshot.has_key is True
    assert snapshot.drivetrain == "All Wheel Drive"
    assert snapshot.vin == "3FMTK4SX8SMA28701"
    assert snapshot.sale_date == datetime(2026, 3, 26, 17, 0, tzinfo=timezone.utc)
    assert snapshot.provider_metadata["branch"] == "Electric Vehicle Auctions"
