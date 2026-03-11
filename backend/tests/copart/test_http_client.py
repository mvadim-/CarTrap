from __future__ import annotations

from pathlib import Path
import sys

import httpx


ROOT = Path(__file__).resolve().parents[2] / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from cartrap.modules.copart_provider.client import COPART_BASE_URL, CopartHttpClient


def test_client_warms_session_and_sends_browser_like_headers() -> None:
    requested_urls: list[str] = []
    target_headers: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        if str(request.url) == f"{COPART_BASE_URL}/":
            return httpx.Response(200, text="<html>home</html>")
        target_headers.update(dict(request.headers))
        return httpx.Response(200, text="<html>lot</html>")

    client = CopartHttpClient(transport=httpx.MockTransport(handler))

    html = client.get_html(f"{COPART_BASE_URL}/lot/12345678")

    assert html == "<html>lot</html>"
    assert requested_urls == [f"{COPART_BASE_URL}/", f"{COPART_BASE_URL}/lot/12345678"]
    assert target_headers["referer"] == f"{COPART_BASE_URL}/"
    assert "Mozilla/5.0" in target_headers["user-agent"]
    assert target_headers["sec-fetch-mode"] == "navigate"


def test_client_continues_after_warmup_failure() -> None:
    requested_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        if str(request.url) == f"{COPART_BASE_URL}/":
            return httpx.Response(403, text="blocked")
        return httpx.Response(200, text="<html>lot</html>")

    client = CopartHttpClient(transport=httpx.MockTransport(handler))

    html = client.get_html(f"{COPART_BASE_URL}/lot/87654321")

    assert html == "<html>lot</html>"
    assert requested_urls == [f"{COPART_BASE_URL}/", f"{COPART_BASE_URL}/lot/87654321"]
