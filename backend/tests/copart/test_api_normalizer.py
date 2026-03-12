from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2] / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from cartrap.modules.copart_provider.normalizer import (
    extract_lot_details,
    extract_search_documents,
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
        "saleStatus": "PURESALE",
        "saleDate": "2026-04-06T14:00:00Z",
        "currentBid": 275,
        "buyTodayBid": 0,
        "currencyCode": "USD",
    }
}


def test_extract_search_documents_returns_docs() -> None:
    documents = extract_search_documents(SAMPLE_RESPONSE)

    assert len(documents) == 2
    assert documents[0]["lot_number"] == 99251295


def test_normalize_search_results_maps_api_fields() -> None:
    results = normalize_search_results(extract_search_documents(SAMPLE_RESPONSE))

    assert len(results) == 2
    assert results[0].lot_number == "99251295"
    assert str(results[0].url) == "https://www.copart.com/lot/99251295"
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


def test_normalize_lot_details_payload_maps_lot_endpoint_fields() -> None:
    snapshot = normalize_lot_details_payload(extract_lot_details(LOT_DETAILS_RESPONSE))

    assert snapshot.lot_number == "76880725"
    assert snapshot.title == "2025 FORD MUSTANG MACH-E GT"
    assert str(snapshot.url) == "https://www.copart.com/lot/76880725"
    assert snapshot.status == "pure_sale"
    assert snapshot.current_bid == 275.0
    assert snapshot.buy_now_price == 0.0
