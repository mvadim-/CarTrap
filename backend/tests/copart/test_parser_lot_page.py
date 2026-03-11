from __future__ import annotations

from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2] / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from cartrap.modules.copart_provider.parser import CopartParseError, parse_lot_page


FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "copart"


def test_parse_lot_page_extracts_snapshot() -> None:
    html = (FIXTURES_DIR / "lot_page.html").read_text()

    snapshot = parse_lot_page(html)

    assert snapshot.lot_number == "12345678"
    assert snapshot.title == "2020 TOYOTA CAMRY SE"
    assert str(snapshot.url) == "https://www.copart.com/lot/12345678"
    assert snapshot.status == "on_approval"
    assert snapshot.current_bid == 4200.0
    assert snapshot.buy_now_price == 6500.0


def test_parse_lot_page_raises_for_missing_payload() -> None:
    html = "<html><body><h1>Missing payload</h1></body></html>"

    with pytest.raises(CopartParseError):
        parse_lot_page(html)
