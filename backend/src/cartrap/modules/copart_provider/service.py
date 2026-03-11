"""Provider facade for Copart scraping operations."""

from __future__ import annotations

from typing import Optional

from cartrap.modules.copart_provider.client import CopartHttpClient
from cartrap.modules.copart_provider.models import CopartLotSnapshot, CopartSearchResult
from cartrap.modules.copart_provider.parser import parse_lot_page, parse_search_results


class CopartProvider:
    def __init__(self, client: Optional[CopartHttpClient] = None) -> None:
        self._client = client or CopartHttpClient()

    def fetch_lot(self, url: str) -> CopartLotSnapshot:
        html = self._client.get_html(url)
        return parse_lot_page(html)

    def search_lots(self, url: str) -> list[CopartSearchResult]:
        html = self._client.get_html(url)
        return parse_search_results(html)

    def close(self) -> None:
        self._client.close()
