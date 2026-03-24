from __future__ import annotations

from pathlib import Path
import sys
import json

import httpx
import pytest


ROOT = Path(__file__).resolve().parents[2] / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from cartrap.config import Settings
from cartrap.modules.copart_provider.client import CopartEncryptedSessionBundle, CopartHttpClient
from cartrap.modules.copart_provider.errors import CopartLoginRejectedError


def make_direct_settings() -> Settings:
    return Settings(
        ENVIRONMENT="test",
        MONGO_URI="mongodb://unused",
        MONGO_DB="cartrap_test",
        COPART_GATEWAY_BASE_URL=None,
        COPART_GATEWAY_TOKEN=None,
        COPART_API_DEVICE_NAME="iPhone 15 Pro Max",
        COPART_API_D_TOKEN="token-123",
        COPART_API_COOKIE="SessionID=abc",
        COPART_API_SITECODE="CPRTUS",
    )


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
        settings=make_direct_settings(),
        transport=httpx.MockTransport(handler),
        base_url="https://mmember.copart.com",
        search_path="/srch/?services=bidIncrementsBySiteV2",
        search_keywords_path="/mcs/v2/public/data/search/keywords",
        lot_details_path="/lots-api/v1/lot-details?services=bidIncrementsBySiteV2",
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


def test_client_search_with_metadata_uses_if_none_match_and_handles_304() -> None:
    captured_headers: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_headers.update(dict(request.headers))
        return httpx.Response(304, headers={"etag": "\"search-etag-2\""})

    client = CopartHttpClient(
        settings=make_direct_settings(),
        transport=httpx.MockTransport(handler),
        base_url="https://mmember.copart.com",
        search_path="/srch/?services=bidIncrementsBySiteV2",
        search_keywords_path="/mcs/v2/public/data/search/keywords",
        lot_details_path="/lots-api/v1/lot-details?services=bidIncrementsBySiteV2",
        device_name="iPhone 15 Pro Max",
        d_token="token-123",
        cookie="SessionID=abc",
        site_code="CPRTUS",
    )

    response = client.search_with_metadata({"MISC": ["lot_number:12345678"], "pageNumber": 1}, etag="\"search-etag-1\"")

    assert response.not_modified is True
    assert response.payload is None
    assert response.etag == "\"search-etag-2\""
    assert captured_headers["if-none-match"] == "\"search-etag-1\""


def test_client_posts_lot_details_payload_with_required_headers() -> None:
    requested_urls: list[str] = []
    captured_body: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        captured_body.update(json.loads(request.content.decode()))
        return httpx.Response(200, json={"lotDetails": {"lotNumber": 76880725}})

    client = CopartHttpClient(
        settings=make_direct_settings(),
        transport=httpx.MockTransport(handler),
        base_url="https://mmember.copart.com",
        search_path="/srch/?services=bidIncrementsBySiteV2",
        search_keywords_path="/mcs/v2/public/data/search/keywords",
        lot_details_path="/lots-api/v1/lot-details?services=bidIncrementsBySiteV2",
        device_name="iPhone 15 Pro Max",
        d_token="token-123",
        cookie="SessionID=abc",
        site_code="CPRTUS",
    )

    response = client.lot_details("76880725")

    assert response["lotDetails"]["lotNumber"] == 76880725
    assert requested_urls == ["https://mmember.copart.com/lots-api/v1/lot-details?services=bidIncrementsBySiteV2"]
    assert captured_body == {"lotNumber": 76880725}


def test_client_lot_details_with_metadata_uses_if_none_match_and_handles_304() -> None:
    captured_headers: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_headers.update(dict(request.headers))
        return httpx.Response(304, headers={"etag": "\"lot-etag-2\""})

    client = CopartHttpClient(
        settings=make_direct_settings(),
        transport=httpx.MockTransport(handler),
        base_url="https://mmember.copart.com",
        search_path="/srch/?services=bidIncrementsBySiteV2",
        search_keywords_path="/mcs/v2/public/data/search/keywords",
        lot_details_path="/lots-api/v1/lot-details?services=bidIncrementsBySiteV2",
        device_name="iPhone 15 Pro Max",
        d_token="token-123",
        cookie="SessionID=abc",
        site_code="CPRTUS",
    )

    response = client.lot_details_with_metadata("76880725", etag="\"lot-etag-1\"")

    assert response.not_modified is True
    assert response.payload is None
    assert response.etag == "\"lot-etag-2\""
    assert captured_headers["if-none-match"] == "\"lot-etag-1\""


def test_client_fetches_search_keywords_with_required_headers() -> None:
    requested_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        return httpx.Response(200, json={"ford": {"type": "MAKE_MODEL"}})

    client = CopartHttpClient(
        settings=make_direct_settings(),
        transport=httpx.MockTransport(handler),
        base_url="https://mmember.copart.com",
        search_path="/srch/?services=bidIncrementsBySiteV2",
        search_keywords_path="/mcs/v2/public/data/search/keywords",
        lot_details_path="/lots-api/v1/lot-details?services=bidIncrementsBySiteV2",
        device_name="iPhone 15 Pro Max",
        d_token="token-123",
        cookie="SessionID=abc",
        site_code="CPRTUS",
    )

    response = client.search_keywords()

    assert response["ford"]["type"] == "MAKE_MODEL"
    assert requested_urls == ["https://mmember.copart.com/mcs/v2/public/data/search/keywords"]


def test_client_requires_api_credentials() -> None:
    client = CopartHttpClient(
        settings=make_direct_settings().model_copy(
            update={
                "copart_api_device_name": "",
                "copart_api_d_token": "",
                "copart_api_cookie": "",
            }
        ),
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={})),
        base_url="https://mmember.copart.com",
        search_path="/srch/?services=bidIncrementsBySiteV2",
        search_keywords_path="/mcs/v2/public/data/search/keywords",
        lot_details_path="/lots-api/v1/lot-details?services=bidIncrementsBySiteV2",
        device_name="",
        d_token="",
        cookie="",
        site_code="CPRTUS",
    )

    with pytest.raises(RuntimeError, match="credentials are not configured"):
        client.search({"MISC": []})


def test_gateway_connector_methods_parse_internal_contract() -> None:
    requests: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append((request.method, str(request.url)))
        if request.url.path == "/v1/connector/bootstrap":
            return httpx.Response(
                200,
                json={
                    "session_bundle": {
                        "encrypted_bundle": "ciphertext",
                        "key_version": "v1",
                        "captured_at": "2026-03-24T17:00:00Z",
                        "expires_at": "2026-12-31T00:00:00Z",
                    },
                    "status": "connected",
                    "verified_at": "2026-03-24T17:00:00Z",
                    "account_label": "user@example.com",
                },
            )
        return httpx.Response(
            200,
            json={
                "payload": {"response": {"docs": [], "numFound": 0}},
                "session_bundle": {
                    "encrypted_bundle": "ciphertext-2",
                    "key_version": "v1",
                    "captured_at": "2026-03-24T17:05:00Z",
                    "expires_at": "2026-12-31T00:00:00Z",
                },
                "status": "connected",
                "verified_at": "2026-03-24T17:05:00Z",
                "used_at": "2026-03-24T17:05:00Z",
            },
        )

    client = CopartHttpClient(
        settings=make_direct_settings().model_copy(
            update={
                "copart_gateway_base_url": "https://gateway.example.test",
                "copart_gateway_token": "gateway-token",
            }
        ),
        transport=httpx.MockTransport(handler),
        base_url="https://gateway.example.test",
        gateway_base_url="https://gateway.example.test",
        gateway_token="gateway-token",
    )
    bundle = CopartEncryptedSessionBundle(
        encrypted_bundle="ciphertext",
        key_version="v1",
    )

    bootstrap = client.bootstrap_connector_session(
        username="user@example.com",
        password="secret",
        client_ip="203.0.113.10",
    )
    search = client.search_with_connector_session({"pageNumber": 1}, bundle)

    assert bootstrap.account_label == "user@example.com"
    assert bootstrap.bundle.encrypted_bundle == "ciphertext"
    assert search.payload == {"response": {"docs": [], "numFound": 0}}
    assert search.bundle.encrypted_bundle == "ciphertext-2"
    assert requests == [
        ("POST", "https://gateway.example.test/v1/connector/bootstrap"),
        ("POST", "https://gateway.example.test/v1/connector/execute/search"),
    ]


def test_direct_connector_bootstrap_uses_seed_d_token_and_me_info_verify_path() -> None:
    requests: list[tuple[str, str, dict[str, str], dict | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(
            (
                request.method,
                str(request.url),
                dict(request.headers),
                json.loads(request.content.decode()) if request.content else None,
            )
        )
        if request.method == "GET" and request.url.path == "/":
            return httpx.Response(200, headers={"set-cookie": "incap_ses_1=edge-cookie; Path=/"})
        if request.method == "POST" and request.url.path == "/mds-api/v1/member/login":
            return httpx.Response(
                200,
                json={"email": "user@example.com"},
                headers={"set-cookie": "SessionID=session-1; Path=/; HttpOnly"},
            )
        if request.method == "GET" and request.url.path == "/mds-api/v1/member/me-info":
            return httpx.Response(
                200,
                json={"memberId": 21438641},
                headers={"set-cookie": "SessionID=session-1; Path=/; HttpOnly"},
            )
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    settings = make_direct_settings().model_copy(
        update={
            "copart_connector_identity_path": None,
            "copart_connector_verify_path": "/mds-api/v1/member/me-info",
        }
    )
    client = CopartHttpClient(
        settings=settings,
        transport=httpx.MockTransport(handler),
        base_url="https://mmember.copart.com",
    )

    bootstrap = client.bootstrap_connector_session(
        username="user@example.com",
        password="secret",
        client_ip="203.0.113.10",
    )

    assert bootstrap.account_label == "user@example.com"
    assert bootstrap.bundle.session_id == "session-1"
    assert bootstrap.bundle.d_token == "token-123"
    login_headers = requests[1][2]
    login_body = requests[1][3]
    assert login_headers["x-d-token"] == "token-123"
    assert login_headers["user-agent"] == "MemberMobile/5 CFNetwork/3860.400.51 Darwin/25.3.0"
    assert login_headers["accept-language"] == "en-US,en;q=0.9"
    assert login_headers["ins-sess"]
    assert login_headers["ip_address"] == "203.0.113.10"
    assert login_body == {
        "username": "user@example.com",
        "password": "secret",
        "keepSession": False,
        "loginLocationInfo": {
            "cityName": "",
            "countryCode": "",
            "countryName": "",
            "latitude": 0.0,
            "longitude": 0.0,
            "registrationSourceCode": "MOBILE",
            "stateCode": "",
            "stateName": "",
            "zipCode": "",
            "ip": "203.0.113.10",
        },
        "anonymousCrmId": login_body["anonymousCrmId"],
    }
    assert isinstance(login_body["anonymousCrmId"], str)
    assert requests[2][1] == "https://mmember.copart.com/mds-api/v1/member/me-info"
    assert requests[2][2]["accept-language"] == "en-US,en;q=0.9"


def test_direct_connector_bootstrap_maps_login_forbidden_to_profile_reject_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/":
            return httpx.Response(200)
        if request.method == "POST" and request.url.path == "/mds-api/v1/member/login":
            return httpx.Response(403, json={"detail": "blocked"})
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    client = CopartHttpClient(
        settings=make_direct_settings(),
        transport=httpx.MockTransport(handler),
        base_url="https://mmember.copart.com",
    )

    with pytest.raises(CopartLoginRejectedError) as exc_info:
        client.bootstrap_connector_session(username="user@example.com", password="secret")

    assert exc_info.value.status_code == 403


def test_gateway_connector_bootstrap_sends_client_ip_to_gateway() -> None:
    captured_json: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_json.update(json.loads(request.content.decode()))
        return httpx.Response(
            200,
            json={
                "session_bundle": {
                    "encrypted_bundle": "ciphertext",
                    "key_version": "v1",
                },
                "status": "connected",
            },
        )

    client = CopartHttpClient(
        settings=make_direct_settings().model_copy(
            update={
                "copart_gateway_base_url": "https://gateway.example.test",
                "copart_gateway_token": "gateway-token",
            }
        ),
        transport=httpx.MockTransport(handler),
        base_url="https://gateway.example.test",
        gateway_base_url="https://gateway.example.test",
        gateway_token="gateway-token",
    )

    client.bootstrap_connector_session(username="user@example.com", password="secret", client_ip="203.0.113.10")

    assert captured_json == {
        "username": "user@example.com",
        "password": "secret",
        "client_ip": "203.0.113.10",
    }
