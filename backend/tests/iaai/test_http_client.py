from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

import httpx


ROOT = Path(__file__).resolve().parents[2] / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from cartrap.config import Settings
from cartrap.modules.iaai_provider.client import IaaiHttpClient
from cartrap.modules.iaai_provider.errors import IaaiAuthenticationError


def test_iaai_client_bootstrap_replays_oidc_login_flow() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == "https://login.test/.well-known/openid-configuration":
            return httpx.Response(
                200,
                json={
                    "authorization_endpoint": "https://login.test/connect/authorize",
                    "token_endpoint": "https://login.test/connect/token",
                },
            )
        if str(request.url).startswith("https://login.test/connect/authorize"):
            return httpx.Response(302, headers={"location": "https://login.test/login"})
        if str(request.url) == "https://login.test/login" and request.method == "GET":
            return httpx.Response(
                200,
                text='<input name="__RequestVerificationToken" type="hidden" value="csrf-123" />',
            )
        if str(request.url) == "https://login.test/login" and request.method == "POST":
            return httpx.Response(302, headers={"location": "mappproxy.iaai.com:/oauth2callback?code=abc123"})
        if str(request.url) == "https://login.test/connect/token":
            return httpx.Response(
                200,
                json={
                    "access_token": "header.payload.signature",
                    "refresh_token": "refresh-1",
                    "expires_in": 3600,
                },
            )
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    settings = Settings(
        IAAI_OIDC_CONFIGURATION_PATH="https://login.test/.well-known/openid-configuration",
        IAAI_OIDC_TOKEN_PATH="https://login.test/connect/token",
    )
    client = IaaiHttpClient(settings=settings, client=httpx.Client(transport=httpx.MockTransport(handler)))

    result = client.bootstrap_connector_session(username="buyer@example.com", password="secret")

    assert result.account_label == "buyer@example.com"
    assert result.connection_status == "connected"
    assert result.bundle.encrypted_bundle


def test_iaai_client_refreshes_expired_token_before_search() -> None:
    calls = {"refresh": 0, "search": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == "https://login.test/connect/token":
            calls["refresh"] += 1
            return httpx.Response(
                200,
                json={
                    "access_token": "header.payload.signature",
                    "refresh_token": "refresh-2",
                    "expires_in": 3600,
                },
            )
        if str(request.url) == "https://api.test/search":
            calls["search"] += 1
            assert request.headers["authorization"] == "Bearer header.payload.signature"
            return httpx.Response(200, json={"vehicles": [], "totalCount": 0})
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    settings = Settings(
        IAAI_OIDC_TOKEN_PATH="https://login.test/connect/token",
        IAAI_MOBILE_SEARCH_PATH="https://api.test/search",
    )
    client = IaaiHttpClient(settings=settings, client=httpx.Client(transport=httpx.MockTransport(handler)))
    bootstrap = client._serialize_bundle(  # noqa: SLF001 - intentional unit-level coverage for bundle replay
        client._build_session_bundle(  # noqa: SLF001
            username="buyer@example.com",
            token_payload={
                "access_token": "expired.token.value",
                "refresh_token": "refresh-1",
                "expires_in": -60,
            },
        )
    )
    bootstrap = bootstrap.__class__(
        encrypted_bundle=bootstrap.encrypted_bundle,
        key_version=bootstrap.key_version,
        captured_at=bootstrap.captured_at,
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),
    )

    result = client.search_with_connector_session({"filters": {}}, bootstrap)

    assert result.payload == {"vehicles": [], "totalCount": 0}
    assert calls == {"refresh": 1, "search": 1}


def test_iaai_client_maps_login_without_code_to_invalid_credentials() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == "https://login.test/.well-known/openid-configuration":
            return httpx.Response(
                200,
                json={
                    "authorization_endpoint": "https://login.test/connect/authorize",
                    "token_endpoint": "https://login.test/connect/token",
                },
            )
        if str(request.url).startswith("https://login.test/connect/authorize"):
            return httpx.Response(302, headers={"location": "https://login.test/login"})
        if str(request.url) == "https://login.test/login" and request.method == "GET":
            return httpx.Response(
                200,
                text='<input name="__RequestVerificationToken" type="hidden" value="csrf-123" />',
            )
        if str(request.url) == "https://login.test/login" and request.method == "POST":
            return httpx.Response(200, text="invalid credentials")
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    settings = Settings(
        IAAI_OIDC_CONFIGURATION_PATH="https://login.test/.well-known/openid-configuration",
        IAAI_OIDC_TOKEN_PATH="https://login.test/connect/token",
    )
    client = IaaiHttpClient(settings=settings, client=httpx.Client(transport=httpx.MockTransport(handler)))

    try:
        client.bootstrap_connector_session(username="buyer@example.com", password="bad-secret")
    except IaaiAuthenticationError:
        return
    raise AssertionError("Expected IaaiAuthenticationError")
