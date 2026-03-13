from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2] / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from cartrap.modules.copart_provider.normalizer import (
    extract_lot_details,
    extract_search_documents,
    extract_search_num_found,
    normalize_lot_details_payload,
    normalize_lot_payload,
    normalize_search_results,
)


SAMPLE_RESPONSE = {
    "response": {
        "numFound": 2,
        "docs": [
            {
                "lot_number": 99251295,
                "lot_desc": "2025 FORD MUSTANG MACH-E PREMIUM",
                "lot_thumbnail_image_path": "https://img.copart.com/99251295.jpg",
                "yard_name": "MI - DETROIT",
                "auction_host_name": "MI - DETROIT",
                "auction_date_utc": "2026-03-13T14:00:00Z",
                "current_high_bid": 0,
                "buy_it_now_price": 11500,
                "currency_code": "USD",
                "salelight_code": "0",
            },
            {
                "lot_number": 76880725,
                "lot_desc": "2025 FORD MUSTANG MACH-E GT",
                "yard_name": "NJ - TRENTON",
                "auction_host_name": "NJ - TRENTON",
                "auction_date_utc": "2026-04-06T14:00:00Z",
                "current_high_bid": 275,
                "buy_it_now_price": 0,
                "currency_code": "USD",
                "salelight_code": "0",
            },
        ],
    }
}

LOT_DETAILS_RESPONSE = {
    "lotDetails": {
        "lotNumber": 76880725,
        "lotDescription": "2025 FORD MUSTANG MACH-E GT",
        "lotImages": [
            {"url": "https://img.copart.com/76880725-detail-1.jpg"},
            {"url": "https://img.copart.com/76880725-detail-2.jpg"},
        ],
        "odometer": {"formattedValue": "12,345 ACTUAL"},
        "primaryDamage": "FRONT END",
        "estRetailValue": 36500,
        "keys": "yes",
        "driveTrain": "AWD",
        "highlights": [
            {"label": "Run and Drive"},
            {"label": "Enhanced Vehicles"},
        ],
        "encryptedVIN": "VnQsUz1aMTpFPlxdCQcFAwU=",
        "saleStatus": "PURESALE",
        "saleDate": "2026-04-06T14:00:00Z",
        "currentBid": 275,
        "buyTodayBid": 0,
        "currencyCode": "USD",
    }
}

LOT_DETAILS_WITH_ROOT_IMAGES_RESPONSE = {
    "lotDetails": {
        "lotNumber": 22223333,
        "lotDescription": "2024 HONDA CR-V EX",
        "saleStatus": "PURESALE",
        "saleDate": "2026-05-06T14:00:00Z",
        "currentBid": 500,
        "buyTodayBid": 0,
        "currencyCode": "USD",
    },
    "lotImages": {
        "heroImages": [
            {"highResUrl": "cs.copart.com/v1/AUTH_svc/22223333_1_ful.jpg"},
            {"highResUrl": "cs.copart.com/v1/AUTH_svc/22223333_2_ful.jpg"},
        ]
    },
}


def test_extract_search_documents_returns_docs() -> None:
    documents = extract_search_documents(SAMPLE_RESPONSE)

    assert len(documents) == 2
    assert documents[0]["lot_number"] == 99251295


def test_extract_search_num_found_returns_total_hit_count() -> None:
    assert extract_search_num_found(SAMPLE_RESPONSE) == 2


def test_normalize_search_results_maps_api_fields() -> None:
    results = normalize_search_results(extract_search_documents(SAMPLE_RESPONSE))

    assert len(results) == 2
    assert results[0].lot_number == "99251295"
    assert str(results[0].url) == "https://www.copart.com/lot/99251295"
    assert str(results[0].thumbnail_url) == "https://img.copart.com/99251295.jpg"
    assert results[0].location == "MI - DETROIT"
    assert results[0].current_bid == 0.0
    assert results[0].currency == "USD"


def test_normalize_lot_payload_maps_single_doc() -> None:
    snapshot = normalize_lot_payload(SAMPLE_RESPONSE["response"]["docs"][1])

    assert snapshot.lot_number == "76880725"
    assert snapshot.title == "2025 FORD MUSTANG MACH-E GT"
    assert str(snapshot.url) == "https://www.copart.com/lot/76880725"
    assert snapshot.current_bid == 275.0
    assert snapshot.buy_now_price == 0.0


def test_extract_lot_details_returns_details_object() -> None:
    details = extract_lot_details(LOT_DETAILS_RESPONSE)

    assert details["lotNumber"] == 76880725


def test_extract_lot_details_merges_root_lot_images() -> None:
    details = extract_lot_details(LOT_DETAILS_WITH_ROOT_IMAGES_RESPONSE)

    assert details["lotNumber"] == 22223333
    assert "lotImages" in details


def test_normalize_lot_details_payload_maps_lot_endpoint_fields() -> None:
    snapshot = normalize_lot_details_payload(extract_lot_details(LOT_DETAILS_RESPONSE))

    assert snapshot.lot_number == "76880725"
    assert snapshot.title == "2025 FORD MUSTANG MACH-E GT"
    assert str(snapshot.url) == "https://www.copart.com/lot/76880725"
    assert str(snapshot.thumbnail_url) == "https://img.copart.com/76880725-detail-1.jpg"
    assert [str(url) for url in snapshot.image_urls] == [
        "https://img.copart.com/76880725-detail-1.jpg",
        "https://img.copart.com/76880725-detail-2.jpg",
    ]
    assert snapshot.odometer == "12,345 ACTUAL"
    assert snapshot.primary_damage == "FRONT END"
    assert snapshot.estimated_retail_value == 36500.0
    assert snapshot.has_key is True
    assert snapshot.drivetrain == "AWD"
    assert snapshot.highlights == ["Run and Drive", "Enhanced Vehicles"]
    assert snapshot.vin == "1FA6P8TH0J5100001"
    assert snapshot.status == "pure_sale"
    assert snapshot.current_bid == 275.0
    assert snapshot.buy_now_price == 0.0


def test_normalize_thumbnail_url_handles_relative_and_protocol_relative_values() -> None:
    results = normalize_search_results(
        [
            {
                "lot_number": 10000001,
                "lot_desc": "2025 TEST LOT",
                "lot_thumbnail_image_path": "/content/lot1.jpg",
                "yard_name": "CA - TEST",
                "currency_code": "USD",
            },
            {
                "lot_number": 10000002,
                "lot_desc": "2025 TEST LOT 2",
                "images": [{"imgUrl": "//img.copart.com/lot2.jpg"}],
                "yard_name": "CA - TEST",
                "currency_code": "USD",
            },
            {
                "lot_number": 10000003,
                "lot_desc": "2025 TEST LOT 3",
                "lot_thumbnail_image_path": "cs.copart.com/v1/AUTH_svc/example_thb.jpg",
                "yard_name": "CA - TEST",
                "currency_code": "USD",
            },
        ]
    )

    assert str(results[0].thumbnail_url) == "https://www.copart.com/content/lot1.jpg"
    assert str(results[1].thumbnail_url) == "https://img.copart.com/lot2.jpg"
    assert str(results[2].thumbnail_url) == "https://cs.copart.com/v1/AUTH_svc/example_thb.jpg"


def test_normalize_lot_details_payload_handles_root_level_gallery_images() -> None:
    snapshot = normalize_lot_details_payload(extract_lot_details(LOT_DETAILS_WITH_ROOT_IMAGES_RESPONSE))

    assert str(snapshot.thumbnail_url) == "https://cs.copart.com/v1/AUTH_svc/22223333_1_ful.jpg"
    assert [str(url) for url in snapshot.image_urls] == [
        "https://cs.copart.com/v1/AUTH_svc/22223333_1_ful.jpg",
        "https://cs.copart.com/v1/AUTH_svc/22223333_2_ful.jpg",
    ]


def test_normalize_lot_details_payload_tolerates_missing_or_invalid_optional_fields() -> None:
    snapshot = normalize_lot_details_payload(
        {
            "lotNumber": 55556666,
            "lotDescription": "2020 TEST LOT",
            "saleStatus": "UPCOMING",
            "estRetailValue": "",
            "keys": "unknown",
            "highlights": "",
            "encryptedVIN": "!!!not-base64!!!",
            "currencyCode": "USD",
        }
    )

    assert snapshot.odometer is None
    assert snapshot.primary_damage is None
    assert snapshot.estimated_retail_value is None
    assert snapshot.has_key is None
    assert snapshot.drivetrain is None
    assert snapshot.highlights == []
    assert snapshot.vin is None
