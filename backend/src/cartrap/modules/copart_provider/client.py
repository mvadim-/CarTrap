"""HTTP client wrapper for Copart JSON API requests."""

from __future__ import annotations

from typing import Optional

import httpx

from cartrap.config import get_settings

DEFAULT_HEADERS = {
    "Content-Type": "application/json; charset=utf-8",
    "Accept": "application/json, text/plain, */*",
    "User-Agent": "/4.5.4 (Macintosh; OS X/26.3.1) GCDHTTPRequest",
}


class CopartHttpClient:
    def __init__(
        self,
        timeout_seconds: float = 15.0,
        headers: Optional[dict[str, str]] = None,
        transport: Optional[httpx.BaseTransport] = None,
        base_url: Optional[str] = None,
        search_path: Optional[str] = None,
        device_name: Optional[str] = None,
        d_token: Optional[str] = None,
        cookie: Optional[str] = None,
        site_code: Optional[str] = None,
    ) -> None:
        settings = get_settings()
        merged_headers = dict(DEFAULT_HEADERS)
        if headers:
            merged_headers.update(headers)
        self._client = httpx.Client(
            base_url=base_url or settings.copart_api_base_url,
            timeout=timeout_seconds,
            headers=merged_headers,
            follow_redirects=True,
            transport=transport,
        )
        self._search_path = search_path or settings.copart_api_search_path
        self._device_name = device_name or settings.copart_api_device_name
        self._d_token = d_token or settings.copart_api_d_token
        self._cookie = cookie or settings.copart_api_cookie
        self._site_code = site_code or settings.copart_api_site_code

    def search(self, payload: dict) -> dict:
        if not self._device_name or not self._d_token or not self._cookie:
            raise RuntimeError("Copart API credentials are not configured.")
        response = self._client.post(
            self._search_path,
            json=payload,
            headers={
                "devicename": self._device_name,
                "x-d-token": self._d_token,
                "Cookie": self._cookie,
                "sitecode": self._site_code,
            },
        )
        response.raise_for_status()
        return response.json()

    def close(self) -> None:
        self._client.close()
