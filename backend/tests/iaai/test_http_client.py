from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

import httpx
import pytest


ROOT = Path(__file__).resolve().parents[2] / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from cartrap.config import Settings
from cartrap.modules.iaai_provider.client import IaaiConnectorBootstrapResult, IaaiHttpClient, IaaiSessionBundle
from cartrap.modules.iaai_provider.errors import IaaiAuthenticationError, IaaiSessionInvalidError, IaaiWafError


def test_iaai_client_bootstrap_replays_oidc_login_flow_with_imperva_preflight() -> None:
    requests: list[tuple[str, str, str | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append((request.method, str(request.url), request.headers.get("cookie")))
        if str(request.url) == "https://login.test/.well-known/openid-configuration":
            return httpx.Response(
                200,
                json={
                    "authorization_endpoint": "https://login.test/connect/authorize",
                    "token_endpoint": "https://login.test/connect/token",
                },
            )
        if str(request.url) == "https://login.test/connect/authorize/callback?state=state-1":
            cookie_header = request.headers.get("cookie") or ""
            assert "idsrv.session=session-1" in cookie_header
            return httpx.Response(302, headers={"location": "https://mappproxy.iaai.com/oauth2callback?code=abc123"})
        if str(request.url).startswith("https://login.test/connect/authorize"):
            assert request.headers["user-agent"].startswith("Mozilla/5.0")
            return httpx.Response(302, headers={"location": "https://login.test/login"})
        if str(request.url) == "https://login.test/login" and request.method == "GET":
            return httpx.Response(
                200,
                text=(
                    '<script src="/A-would-they-here-beathe-and-should-mis-fore-Cas" async></script>'
                    '<input name="__RequestVerificationToken" type="hidden" value="csrf-123" />'
                ),
                headers={"set-cookie": "reese84=token-1; Path=/; Domain=.login.test"},
            )
        if str(request.url) == "https://login.test/A-would-they-here-beathe-and-should-mis-fore-Cas" and request.method == "GET":
            assert request.headers["referer"] == "https://login.test/login"
            return httpx.Response(304)
        if str(request.url) == "https://login.test/A-would-they-here-beathe-and-should-mis-fore-Cas?d=login.iaai.com":
            assert request.method == "POST"
            assert request.content == b'"token-1"'
            assert "reese84=token-1" in (request.headers.get("cookie") or "")
            return httpx.Response(
                200,
                json={"token": "token-1"},
                headers={"set-cookie": "nlbi_2831003_2147483392=lb-1; Path=/; Domain=.login.test"},
            )
        if str(request.url) == "https://login.test/login" and request.method == "POST":
            cookie_header = request.headers.get("cookie") or ""
            assert "reese84=token-1" in cookie_header
            assert "nlbi_2831003_2147483392=lb-1" in cookie_header
            assert request.headers["origin"] == "https://login.iaai.com"
            return httpx.Response(
                302,
                headers={
                    "location": "/connect/authorize/callback?state=state-1",
                    "set-cookie": "idsrv.session=session-1; Path=/; Domain=.login.test",
                },
            )
        if str(request.url) == "https://login.test/connect/token":
            assert request.headers["user-agent"].startswith("IAA Buyer/1")
            assert request.headers["content-type"] == "application/x-www-form-urlencoded; charset=UTF-8"
            return httpx.Response(
                200,
                json={
                    "access_token": "header.payload.signature",
                    "refresh_token": "refresh-1",
                    "expires_in": 3600,
                },
                headers={"set-cookie": "incap_ses_323_2831003=imperva-1; Path=/; Domain=.login.test"},
            )
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    settings = Settings(
        IAAI_OIDC_CONFIGURATION_PATH="https://login.test/.well-known/openid-configuration",
        IAAI_OIDC_TOKEN_PATH="https://login.test/connect/token",
        IAAI_BROWSER_BOOTSTRAP_ENABLED=False,
    )
    client = IaaiHttpClient(settings=settings, client=httpx.Client(transport=httpx.MockTransport(handler)))

    result = client.bootstrap_connector_session(username="buyer@example.com", password="secret", client_ip="203.0.113.10")

    assert result.account_label == "buyer@example.com"
    assert result.connection_status == "connected"
    bundle = client._require_bundle(result.bundle)  # noqa: SLF001 - unit-level bundle contract coverage
    cookie_names = {name for name, _ in bundle.cookies}
    assert {"reese84", "nlbi_2831003_2147483392", "idsrv.session", "incap_ses_323_2831003"} <= cookie_names
    assert bundle.header_profile.request_type == "IAA-Buyer-App-iOS"
    assert bundle.header_profile.app_version == "295"
    assert bundle.header_profile.device_type == "IOS"
    assert bundle.header_profile.session_id
    assert all("x-ipaddress" not in dict_ for dict_ in (dict(httpx.Headers({"cookie": cookie or ""})) for _, _, cookie in requests))


def test_iaai_client_bootstrap_uses_script_body_token_when_cookie_is_missing() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == "https://login.test/.well-known/openid-configuration":
            return httpx.Response(
                200,
                json={
                    "authorization_endpoint": "https://login.test/connect/authorize",
                    "token_endpoint": "https://login.test/connect/token",
                },
            )
        if str(request.url) == "https://login.test/connect/authorize/callback?state=state-1":
            return httpx.Response(302, headers={"location": "https://mappproxy.iaai.com/oauth2callback?code=abc123"})
        if str(request.url).startswith("https://login.test/connect/authorize"):
            return httpx.Response(302, headers={"location": "https://login.test/login"})
        if str(request.url) == "https://login.test/login" and request.method == "GET":
            return httpx.Response(
                200,
                text=(
                    '<script src="/A-would-they-here-beathe-and-should-mis-fore-Cas" async></script>'
                    '<input name="__RequestVerificationToken" type="hidden" value="csrf-123" />'
                ),
            )
        if str(request.url) == "https://login.test/A-would-they-here-beathe-and-should-mis-fore-Cas" and request.method == "GET":
            return httpx.Response(200, text='{"token":"body-token-1"}', headers={"content-type": "application/json"})
        if str(request.url) == "https://login.test/A-would-they-here-beathe-and-should-mis-fore-Cas?d=login.iaai.com":
            assert request.content == b'"body-token-1"'
            return httpx.Response(
                200,
                json={"token": "body-token-1"},
                headers={"set-cookie": "nlbi_2831003_2147483392=lb-1; Path=/; Domain=.login.test"},
            )
        if str(request.url) == "https://login.test/login" and request.method == "POST":
            return httpx.Response(302, headers={"location": "/connect/authorize/callback?state=state-1"})
        if str(request.url) == "https://login.test/connect/token":
            return httpx.Response(
                200,
                json={
                    "access_token": "header.payload.signature",
                    "refresh_token": "refresh-1",
                    "expires_in": 3600,
                },
                headers={"set-cookie": "incap_ses_323_2831003=imperva-1; Path=/; Domain=.login.test"},
            )
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    settings = Settings(
        IAAI_OIDC_CONFIGURATION_PATH="https://login.test/.well-known/openid-configuration",
        IAAI_OIDC_TOKEN_PATH="https://login.test/connect/token",
        IAAI_BROWSER_BOOTSTRAP_ENABLED=False,
    )
    client = IaaiHttpClient(settings=settings, client=httpx.Client(transport=httpx.MockTransport(handler)))

    result = client.bootstrap_connector_session(username="buyer@example.com", password="secret")

    assert result.connection_status == "connected"


def test_iaai_client_bootstrap_falls_back_to_browser_flow_when_imperva_cookie_never_appears(monkeypatch: pytest.MonkeyPatch) -> None:
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
                text=(
                    '<script src="/A-would-they-here-beathe-and-should-mis-fore-Cas" async></script>'
                    '<input name="__RequestVerificationToken" type="hidden" value="csrf-123" />'
                ),
            )
        if str(request.url) == "https://login.test/A-would-they-here-beathe-and-should-mis-fore-Cas":
            return httpx.Response(200, text="window.__imperva = {};", headers={"content-type": "text/javascript"})
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    settings = Settings(
        IAAI_OIDC_CONFIGURATION_PATH="https://login.test/.well-known/openid-configuration",
        IAAI_OIDC_TOKEN_PATH="https://login.test/connect/token",
        IAAI_BROWSER_BOOTSTRAP_ENABLED=True,
    )
    client = IaaiHttpClient(settings=settings, client=httpx.Client(transport=httpx.MockTransport(handler)))

    def fake_browser_bootstrap(*, username: str, password: str, correlation_id: str, metadata: dict) -> IaaiConnectorBootstrapResult:
        assert username == "buyer@example.com"
        assert password == "secret"
        assert correlation_id.startswith("iaai-bootstrap-")
        assert metadata["token_endpoint"] == "https://login.test/connect/token"
        return IaaiConnectorBootstrapResult(
            bundle=client._serialize_bundle(  # noqa: SLF001 - explicit fallback contract coverage
                client._build_session_bundle(  # noqa: SLF001
                    username=username,
                    token_payload={
                        "access_token": "header.payload.signature",
                        "refresh_token": "refresh-1",
                        "expires_in": 3600,
                    },
                )
            ),
            account_label=username,
            connection_status="connected",
            verified_at=datetime.now(timezone.utc),
        )

    monkeypatch.setattr(client, "_bootstrap_connector_session_with_browser", fake_browser_bootstrap)

    result = client.bootstrap_connector_session(username="buyer@example.com", password="secret")

    assert result.connection_status == "connected"
    assert result.account_label == "buyer@example.com"


def test_iaai_client_rejects_missing_imperva_state() -> None:
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
        if str(request.url) == "https://login.test/login":
            return httpx.Response(
                200,
                text=(
                    '<script src="/A-would-they-here-beathe-and-should-mis-fore-Cas" async></script>'
                    '<input name="__RequestVerificationToken" type="hidden" value="csrf-123" />'
                ),
            )
        if str(request.url) == "https://login.test/A-would-they-here-beathe-and-should-mis-fore-Cas":
            return httpx.Response(304)
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    settings = Settings(
        IAAI_OIDC_CONFIGURATION_PATH="https://login.test/.well-known/openid-configuration",
        IAAI_OIDC_TOKEN_PATH="https://login.test/connect/token",
        IAAI_BROWSER_BOOTSTRAP_ENABLED=False,
    )
    client = IaaiHttpClient(settings=settings, client=httpx.Client(transport=httpx.MockTransport(handler)))

    with pytest.raises(IaaiWafError) as excinfo:
        client.bootstrap_connector_session(username="buyer@example.com", password="secret")

    assert excinfo.value.diagnostics is not None
    assert excinfo.value.diagnostics.step == "imperva_preflight"
    assert excinfo.value.diagnostics.hint == "missing_reese84_cookie_after_script_get"


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
                headers={"set-cookie": "incap_ses_323_2831003=imperva-rotated; Path=/; Domain=.api.test"},
            )
        if str(request.url) == "https://api.test/search":
            calls["search"] += 1
            assert request.headers["authorization"] == "Bearer header.payload.signature"
            assert request.headers["x-request-type"] == "IAA-Buyer-App-iOS"
            assert "incap_ses_323_2831003=imperva-1" in request.headers["cookie"]
            return httpx.Response(200, json={"vehicles": [], "totalCount": 0})
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    settings = Settings(
        IAAI_OIDC_TOKEN_PATH="https://login.test/connect/token",
        IAAI_MOBILE_SEARCH_PATH="https://api.test/search",
    )
    client = IaaiHttpClient(settings=settings, client=httpx.Client(transport=httpx.MockTransport(handler)))
    seed_bundle = client._build_session_bundle(  # noqa: SLF001 - intentional unit-level coverage for bundle replay
        username="buyer@example.com",
        token_payload={
            "access_token": "expired.token.value",
            "refresh_token": "refresh-1",
            "expires_in": -60,
        },
    )
    bundle_with_cookies = IaaiSessionBundle(
        access_token=seed_bundle.access_token,
        refresh_token=seed_bundle.refresh_token,
        expires_at=seed_bundle.expires_at,
        account_label=seed_bundle.account_label,
        user_id=seed_bundle.user_id,
        cookies=(("incap_ses_323_2831003", "imperva-1"), ("visid_incap_2831003", "visid-1")),
        header_profile=seed_bundle.header_profile,
        captured_at=seed_bundle.captured_at,
    )
    bootstrap = client._serialize_bundle(bundle_with_cookies)  # noqa: SLF001
    bootstrap = bootstrap.__class__(
        encrypted_bundle=bootstrap.encrypted_bundle,
        key_version=bootstrap.key_version,
        captured_at=bootstrap.captured_at,
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),
    )

    result = client.search_with_connector_session({"filters": {}}, bootstrap)

    assert result.payload == {"vehicles": [], "totalCount": 0}
    assert calls == {"refresh": 1, "search": 1}


def test_iaai_client_rejects_incomplete_bundle_before_execute() -> None:
    settings = Settings(IAAI_MOBILE_SEARCH_PATH="https://api.test/search")
    client = IaaiHttpClient(settings=settings, client=httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200))))
    bundle = IaaiSessionBundle(
        access_token="token-1",
        refresh_token="refresh-1",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        account_label="buyer@example.com",
        user_id="user-1",
        cookies=(),
        header_profile=client._build_session_bundle(  # noqa: SLF001
            username="buyer@example.com",
            token_payload={"access_token": "token-1", "refresh_token": "refresh-1", "expires_in": 3600},
        ).header_profile,
        captured_at=datetime.now(timezone.utc),
    )

    with pytest.raises(IaaiSessionInvalidError, match="anti-bot cookies"):
        client.search_with_connector_session({"filters": {}}, bundle)


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
                text=(
                    '<script src="/A-would-they-here-beathe-and-should-mis-fore-Cas" async></script>'
                    '<input name="__RequestVerificationToken" type="hidden" value="csrf-123" />'
                ),
                headers={"set-cookie": "reese84=token-1; Path=/; Domain=.login.test"},
            )
        if str(request.url) == "https://login.test/A-would-they-here-beathe-and-should-mis-fore-Cas" and request.method == "GET":
            return httpx.Response(304)
        if str(request.url) == "https://login.test/A-would-they-here-beathe-and-should-mis-fore-Cas?d=login.iaai.com":
            return httpx.Response(
                200,
                json={"token": "token-1"},
                headers={"set-cookie": "nlbi_2831003_2147483392=lb-1; Path=/; Domain=.login.test"},
            )
        if str(request.url) == "https://login.test/login" and request.method == "POST":
            return httpx.Response(200, text="invalid credentials")
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    settings = Settings(
        IAAI_OIDC_CONFIGURATION_PATH="https://login.test/.well-known/openid-configuration",
        IAAI_OIDC_TOKEN_PATH="https://login.test/connect/token",
    )
    client = IaaiHttpClient(settings=settings, client=httpx.Client(transport=httpx.MockTransport(handler)))

    with pytest.raises(IaaiAuthenticationError) as excinfo:
        client.bootstrap_connector_session(username="buyer@example.com", password="bad-secret")

    assert excinfo.value.diagnostics is not None
    assert excinfo.value.diagnostics.step == "login_submit"
