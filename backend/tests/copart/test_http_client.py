from __future__ import annotations

from pathlib import Path
import sys
import json

import httpx
import pytest


ROOT = Path(__file__).resolve().parents[2] / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from cartrap.modules.copart_provider.client import CopartHttpClient


def test_client_posts_json_payload_with_required_headers() -> None:
    requested_urls: list[str] = []
    captured_headers: dict[str, str] = {}
    captured_body: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        captured_headers.update(dict(request.headers))
        captured_body.update(json.loads(request.content.decode()))
        return httpx.Response(200, json={"response": {"numFound": 0, "docs": []}})

    client = CopartHttpClient(
        transport=httpx.MockTransport(handler),
        base_url="https://mmember.copart.com",
        search_path="/srch/?services=bidIncrementsBySiteV2",
        device_name="iPhone 15 Pro Max",
        d_token="token-123",
        cookie="SessionID=abc",
        site_code="CPRTUS",
    )

    response = client.search({"MISC": ["lot_number:12345678"], "pageNumber": 1})

    assert response["response"]["docs"] == []
    assert requested_urls == ["https://mmember.copart.com/srch/?services=bidIncrementsBySiteV2"]
    assert captured_headers["devicename"] == "iPhone 15 Pro Max"
    assert captured_headers["x-d-token"] == "token-123"
    assert captured_headers["cookie"] == "SessionID=abc"
    assert captured_headers["sitecode"] == "CPRTUS"
    assert captured_body == {"MISC": ["lot_number:12345678"], "pageNumber": 1}


def test_client_requires_api_credentials() -> None:
    client = CopartHttpClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={})),
        base_url="https://mmember.copart.com",
        search_path="/srch/?services=bidIncrementsBySiteV2",
        device_name=None,
        d_token=None,
        cookie=None,
        site_code="CPRTUS",
    )

    with pytest.raises(RuntimeError, match="credentials are not configured"):
        client.search({"MISC": []})
