from __future__ import annotations

from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2] / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from cartrap.modules.copart_provider.parser import CopartParseError, parse_search_results


FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "copart"


def test_parse_search_results_extracts_lots() -> None:
    html = (FIXTURES_DIR / "search_results.html").read_text()

    results = parse_search_results(html)

    assert len(results) == 2
    assert results[0].lot_number == "12345678"
    assert results[0].status == "live"
    assert results[1].lot_number == "87654321"
    assert results[1].current_bid == 1800.0


def test_parse_search_results_raises_for_missing_payload() -> None:
    html = "<html><body><div>No script data</div></body></html>"

    with pytest.raises(CopartParseError):
        parse_search_results(html)
