from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2] / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from cartrap.modules.auction_domain.models import (
    AuctionSearchResult,
    backfill_lot_identity,
    build_lot_key,
)


def test_build_lot_key_uses_provider_specific_identity() -> None:
    assert build_lot_key("copart", "12345678") == "copart:12345678"
    assert build_lot_key("iaai", "12345678") == "iaai:12345678"


def test_backfill_lot_identity_defaults_legacy_copart_payload() -> None:
    payload = backfill_lot_identity({"lot_number": "87654321", "title": "Legacy"})

    assert payload["provider"] == "copart"
    assert payload["provider_lot_id"] == "87654321"
    assert payload["lot_key"] == "copart:87654321"


def test_search_result_keeps_same_lot_number_distinct_across_providers() -> None:
    copart = AuctionSearchResult(provider="copart", provider_lot_id="12345678", lot_number="12345678", title="A")
    iaai = AuctionSearchResult(provider="iaai", provider_lot_id="12345678", lot_number="12345678", title="B")

    assert copart.lot_key == "copart:12345678"
    assert iaai.lot_key == "iaai:12345678"
    assert copart.lot_key != iaai.lot_key
