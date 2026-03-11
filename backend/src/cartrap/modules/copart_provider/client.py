"""HTTP client wrapper for Copart requests."""

from __future__ import annotations

import importlib.util
import logging
from typing import Optional

import httpx


logger = logging.getLogger(__name__)
COPART_BASE_URL = "https://www.copart.com"
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,"
        "image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "max-age=0",
    "Sec-CH-UA": '"Chromium";v="132", "Google Chrome";v="132", "Not A(Brand";v="24"',
    "Sec-CH-UA-Mobile": "?0",
    "Sec-CH-UA-Platform": '"macOS"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}


class CopartHttpClient:
    def __init__(
        self,
        timeout_seconds: float = 15.0,
        headers: Optional[dict[str, str]] = None,
        transport: Optional[httpx.BaseTransport] = None,
    ) -> None:
        merged_headers = dict(DEFAULT_HEADERS)
        if headers:
            merged_headers.update(headers)
        http2_enabled = importlib.util.find_spec("h2") is not None
        self._client = httpx.Client(
            timeout=timeout_seconds,
            headers=merged_headers,
            follow_redirects=True,
            http2=http2_enabled,
            transport=transport,
        )
        self._session_warmed_up = False

    def get_html(self, url: str) -> str:
        self._warm_up_session()
        response = self._client.get(url, headers={"Referer": f"{COPART_BASE_URL}/"})
        response.raise_for_status()
        return response.text

    def close(self) -> None:
        self._client.close()

    def _warm_up_session(self) -> None:
        if self._session_warmed_up:
            return
        try:
            response = self._client.get(f"{COPART_BASE_URL}/")
            response.raise_for_status()
        except Exception:
            logger.warning("Copart session warmup failed before target fetch.", exc_info=True)
        finally:
            self._session_warmed_up = True
