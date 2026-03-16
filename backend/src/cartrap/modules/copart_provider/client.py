"""HTTP client wrapper for Copart JSON API requests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import httpx

from cartrap.config import get_settings

DEFAULT_HEADERS = {
    "Content-Type": "application/json; charset=utf-8",
    "Accept": "application/json, text/plain, */*",
    "User-Agent": "/4.5.4 (Macintosh; OS X/26.3.1) GCDHTTPRequest",
}


@dataclass
class CopartHttpPayloadResponse:
    payload: Optional[dict]
    etag: Optional[str]
    not_modified: bool = False


class CopartHttpClient:
    def __init__(
        self,
        timeout_seconds: float = 15.0,
        headers: Optional[dict[str, str]] = None,
        transport: Optional[httpx.BaseTransport] = None,
        base_url: Optional[str] = None,
        search_path: Optional[str] = None,
        search_keywords_path: Optional[str] = None,
        lot_details_path: Optional[str] = None,
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
        self._search_path = settings.copart_api_search_path if search_path is None else search_path
        self._search_keywords_path = (
            settings.copart_api_search_keywords_path if search_keywords_path is None else search_keywords_path
        )
        self._lot_details_path = (
            settings.copart_api_lot_details_path if lot_details_path is None else lot_details_path
        )
        self._device_name = settings.copart_api_device_name if device_name is None else device_name
        self._d_token = settings.copart_api_d_token if d_token is None else d_token
        self._cookie = settings.copart_api_cookie if cookie is None else cookie
        self._site_code = settings.copart_api_site_code if site_code is None else site_code

    def search(self, payload: dict) -> dict:
        response = self.search_with_metadata(payload)
        if response.not_modified or response.payload is None:
            raise RuntimeError("Search payload is not available for a 304 response.")
        return response.payload

    def search_with_metadata(self, payload: dict, etag: Optional[str] = None) -> CopartHttpPayloadResponse:
        return self._request_json("POST", self._search_path, json=payload, etag=etag)

    def lot_details(self, lot_number: str) -> dict:
        response = self.lot_details_with_metadata(lot_number)
        if response.not_modified or response.payload is None:
            raise RuntimeError("Lot details payload is not available for a 304 response.")
        return response.payload

    def lot_details_with_metadata(self, lot_number: str, etag: Optional[str] = None) -> CopartHttpPayloadResponse:
        return self._request_json("POST", self._lot_details_path, json={"lotNumber": int(lot_number)}, etag=etag)

    def search_keywords(self) -> dict:
        response = self._client.get(self._search_keywords_path, headers=self._auth_headers())
        response.raise_for_status()
        return response.json()

    def close(self) -> None:
        self._client.close()

    def _auth_headers(self) -> dict[str, str]:
        if not self._device_name or not self._d_token or not self._cookie:
            raise RuntimeError("Copart API credentials are not configured.")
        return {
            "devicename": self._device_name,
            "x-d-token": self._d_token,
            "Cookie": self._cookie,
            "sitecode": self._site_code,
        }

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        json: Optional[dict] = None,
        etag: Optional[str] = None,
    ) -> CopartHttpPayloadResponse:
        headers = self._auth_headers()
        if etag:
            headers["If-None-Match"] = etag
        response = self._client.request(method, path, json=json, headers=headers)
        if response.status_code == httpx.codes.NOT_MODIFIED:
            return CopartHttpPayloadResponse(payload=None, etag=response.headers.get("etag") or etag, not_modified=True)
        response.raise_for_status()
        return CopartHttpPayloadResponse(payload=response.json(), etag=response.headers.get("etag"), not_modified=False)
