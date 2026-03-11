"""HTTP client wrapper for Copart requests."""

from __future__ import annotations

from typing import Optional

import httpx


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


class CopartHttpClient:
    def __init__(
        self,
        timeout_seconds: float = 15.0,
        headers: Optional[dict[str, str]] = None,
    ) -> None:
        merged_headers = dict(DEFAULT_HEADERS)
        if headers:
            merged_headers.update(headers)
        self._client = httpx.Client(timeout=timeout_seconds, headers=merged_headers, follow_redirects=True)

    def get_html(self, url: str) -> str:
        response = self._client.get(url)
        response.raise_for_status()
        return response.text

    def close(self) -> None:
        self._client.close()
