"""Transport-aware IAAI client facade for direct and gateway-backed requests."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import logging
import re
from typing import Any, Optional
from urllib.parse import parse_qs, urljoin, urlparse
from uuid import uuid4

import httpx

from cartrap.config import Settings, get_settings
from cartrap.core.logging import make_log_extra, new_correlation_id
from cartrap.modules.iaai_provider.errors import (
    IaaiAuthenticationError,
    IaaiConfigurationError,
    IaaiDiagnostics,
    IaaiGatewayMalformedResponseError,
    IaaiGatewayUnavailableError,
    IaaiRefreshError,
    IaaiSessionInvalidError,
    IaaiWafError,
)


OIDC_SCOPE = "openid profile email offline_access BuyerProfileClaims"
GATEWAY_SEARCH_PATH = "/v1/search"
GATEWAY_LOT_DETAILS_PATH = "/v1/lot-details"
GATEWAY_CONNECTOR_BOOTSTRAP_PATH = "/v1/connector/bootstrap"
GATEWAY_CONNECTOR_VERIFY_PATH = "/v1/connector/verify"
GATEWAY_CONNECTOR_EXECUTE_SEARCH_PATH = "/v1/connector/execute/search"
GATEWAY_CONNECTOR_EXECUTE_LOT_DETAILS_PATH = "/v1/connector/execute/lot-details"
GATEWAY_ERROR_HEADER = "x-iaai-gateway-error"
GATEWAY_UPSTREAM_STATUS_HEADER = "x-iaai-upstream-status"
GATEWAY_CORRELATION_ID_HEADER = "x-iaai-correlation-id"
GATEWAY_STEP_HEADER = "x-iaai-bootstrap-step"
GATEWAY_FAILURE_CLASS_HEADER = "x-iaai-failure-class"
REQUEST_CORRELATION_ID_HEADER = "x-correlation-id"
STEP_OIDC_METADATA = "oidc_metadata"
STEP_AUTHORIZE = "authorize"
STEP_LOGIN_PAGE = "login_page"
STEP_IMPERVA_PREFLIGHT = "imperva_preflight"
STEP_LOGIN_SUBMIT = "login_submit"
STEP_AUTHORIZE_CALLBACK = "authorize_callback"
STEP_TOKEN_EXCHANGE = "token_exchange"
IMPERVA_SCRIPT_DOMAIN_PARAM = "login.iaai.com"
IMPERVA_COOKIE_NAME = "reese84"
AUTHENTICATED_COOKIE_PREFIXES = ("incap_ses_", "visid_incap_", "nlbi_", "ARRAffinity")
REQUEST_TIMEOUT_HINT = "timeout"
WAF_HINT = "imperva_or_waf"
INVALID_CREDENTIALS_HINT = "missing_authorization_code"
BROWSER_FALLBACK_HINTS = {
    "missing_reese84_cookie_after_script_get",
    "missing_imperva_post_state",
}


logger = logging.getLogger(__name__)


@dataclass
class IaaiHttpPayloadResponse:
    payload: Optional[dict]
    etag: Optional[str]
    not_modified: bool = False


@dataclass(frozen=True)
class IaaiHeaderProfile:
    tenant: str
    apikey: str
    deviceid: str
    request_type: str
    app_version: str
    country: str
    language: str
    user_agent: str
    device_type: str | None = None
    os_version: str | None = None
    model_name: str | None = None
    session_id: str | None = None

    def to_headers(self, *, access_token: str, user_id: str | None, extra_cookies: tuple[tuple[str, str], ...]) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "tenant": self.tenant,
            "apikey": self.apikey,
            "deviceid": self.deviceid,
            "x-request-type": self.request_type,
            "x-app-version": self.app_version,
            "appversion": self.app_version,
            "x-country": self.country,
            "x-language": _mobile_language_code(self.language),
            "x-datetime": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "User-Agent": self.user_agent,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": f"{self.language},en;q=0.9",
        }
        if self.session_id:
            headers["x-session"] = self.session_id
        if self.device_type:
            headers["x-device-type"] = self.device_type
            headers["devicetype"] = self.device_type
        if self.os_version:
            headers["x-os-version"] = self.os_version
        if self.model_name:
            headers["x-model-name"] = self.model_name
        if user_id:
            headers["x-user-id"] = user_id
        if extra_cookies:
            headers["Cookie"] = "; ".join(f"{name}={value}" for name, value in extra_cookies if value)
        return headers

    def to_payload(self) -> dict[str, str]:
        return {
            "tenant": self.tenant,
            "apikey": self.apikey,
            "deviceid": self.deviceid,
            "request_type": self.request_type,
            "app_version": self.app_version,
            "country": self.country,
            "language": self.language,
            "user_agent": self.user_agent,
            "device_type": self.device_type,
            "os_version": self.os_version,
            "model_name": self.model_name,
            "session_id": self.session_id,
        }

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "IaaiHeaderProfile":
        return cls(
            tenant=str(payload["tenant"]),
            apikey=str(payload["apikey"]),
            deviceid=str(payload["deviceid"]),
            request_type=str(payload["request_type"]),
            app_version=str(payload["app_version"]),
            country=str(payload["country"]),
            language=str(payload["language"]),
            user_agent=str(payload["user_agent"]),
            device_type=(str(payload["device_type"]) if payload.get("device_type") else None),
            os_version=(str(payload["os_version"]) if payload.get("os_version") else None),
            model_name=(str(payload["model_name"]) if payload.get("model_name") else None),
            session_id=(str(payload["session_id"]) if payload.get("session_id") else None),
        )


@dataclass(frozen=True)
class IaaiSessionBundle:
    access_token: str
    refresh_token: Optional[str]
    expires_at: Optional[datetime]
    account_label: Optional[str]
    user_id: Optional[str]
    cookies: tuple[tuple[str, str], ...]
    header_profile: IaaiHeaderProfile
    captured_at: Optional[datetime] = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "account_label": self.account_label,
            "user_id": self.user_id,
            "cookies": [{"name": name, "value": value} for name, value in self.cookies],
            "header_profile": self.header_profile.to_payload(),
            "captured_at": self.captured_at.isoformat() if self.captured_at else None,
        }

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "IaaiSessionBundle":
        return cls(
            access_token=str(payload["access_token"]),
            refresh_token=(str(payload["refresh_token"]) if payload.get("refresh_token") else None),
            expires_at=_parse_optional_datetime(payload.get("expires_at")),
            account_label=(str(payload["account_label"]) if payload.get("account_label") else None),
            user_id=(str(payload["user_id"]) if payload.get("user_id") else None),
            cookies=tuple((str(item["name"]), str(item["value"])) for item in payload.get("cookies", [])),
            header_profile=IaaiHeaderProfile.from_payload(payload["header_profile"]),
            captured_at=_parse_optional_datetime(payload.get("captured_at")),
        )


@dataclass(frozen=True)
class IaaiEncryptedSessionBundle:
    encrypted_bundle: str
    key_version: str
    captured_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "encrypted_bundle": self.encrypted_bundle,
            "key_version": self.key_version,
            "captured_at": self.captured_at.isoformat() if self.captured_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "IaaiEncryptedSessionBundle":
        return cls(
            encrypted_bundle=str(payload["encrypted_bundle"]),
            key_version=str(payload["key_version"]),
            captured_at=_parse_optional_datetime(payload.get("captured_at")),
            expires_at=_parse_optional_datetime(payload.get("expires_at")),
        )


@dataclass
class IaaiConnectorBootstrapResult:
    bundle: object
    account_label: Optional[str]
    connection_status: str
    verified_at: Optional[datetime]


@dataclass
class IaaiConnectorExecutionResult:
    payload: Optional[dict]
    bundle: Optional[object]
    etag: Optional[str]
    not_modified: bool
    connection_status: str
    verified_at: Optional[datetime]
    used_at: Optional[datetime]


class IaaiHttpClient:
    def __init__(
        self,
        settings: Optional[Settings] = None,
        client: Optional[httpx.Client] = None,
        transport: Optional[httpx.BaseTransport] = None,
        gateway_base_url: Optional[str] = None,
        gateway_token: Optional[str] = None,
        gateway_enable_gzip: Optional[bool] = None,
    ) -> None:
        resolved_settings = settings or get_settings()
        if gateway_base_url is not None or gateway_token is not None:
            resolved_settings = resolved_settings.model_copy(
                update={
                    "iaai_gateway_base_url": gateway_base_url,
                    "iaai_gateway_token": gateway_token,
                    "iaai_gateway_enable_gzip": (
                        resolved_settings.iaai_gateway_enable_gzip
                        if gateway_enable_gzip is None
                        else gateway_enable_gzip
                    ),
                }
            )
        elif gateway_enable_gzip is not None:
            resolved_settings = resolved_settings.model_copy(update={"iaai_gateway_enable_gzip": gateway_enable_gzip})

        self._settings = resolved_settings
        self._gateway_enabled = resolved_settings.iaai_gateway_enabled
        if client is not None:
            self._client = client
            return

        if self._gateway_enabled:
            if not resolved_settings.iaai_gateway_token:
                raise IaaiConfigurationError("IAAI gateway token is not configured.")
            headers = {
                "Authorization": f"Bearer {resolved_settings.iaai_gateway_token}",
                "Accept": "application/json, text/plain, */*",
            }
            if resolved_settings.iaai_gateway_enable_gzip:
                headers["Accept-Encoding"] = "gzip"
            self._client = httpx.Client(
                base_url=resolved_settings.iaai_gateway_base_url,
                follow_redirects=True,
                timeout=httpx.Timeout(
                    resolved_settings.iaai_http_timeout_seconds,
                    connect=resolved_settings.iaai_http_connect_timeout_seconds,
                ),
                headers=headers,
                transport=transport,
            )
            return

        self._client = httpx.Client(
            follow_redirects=False,
            timeout=httpx.Timeout(
                resolved_settings.iaai_http_timeout_seconds,
                connect=resolved_settings.iaai_http_connect_timeout_seconds,
            ),
            headers={
                "Accept-Language": resolved_settings.iaai_mobile_language,
                "User-Agent": resolved_settings.iaai_mobile_user_agent,
            },
            transport=transport,
        )

    def bootstrap_connector_session(
        self,
        *,
        username: str,
        password: str,
        client_ip: str | None = None,
        correlation_id: str | None = None,
    ) -> IaaiConnectorBootstrapResult:
        cid = correlation_id or new_correlation_id("iaai-bootstrap")
        if self._gateway_enabled:
            response = self._request_gateway_json(
                "POST",
                GATEWAY_CONNECTOR_BOOTSTRAP_PATH,
                json={
                    "username": username,
                    "password": password,
                    "client_ip": client_ip,
                },
                correlation_id=cid,
            )
            payload = response.payload or {}
            return IaaiConnectorBootstrapResult(
                bundle=IaaiEncryptedSessionBundle.from_payload(payload["session_bundle"]),
                account_label=(str(payload["account_label"]) if payload.get("account_label") else None),
                connection_status=str(payload.get("status") or "connected"),
                verified_at=_parse_optional_datetime(payload.get("verified_at")),
            )
        if client_ip:
            # IAAI sees the NAS gateway IP anyway, so forwarding a synthetic client IP is misleading and was
            # not present in the captured login flow. We keep the parameter for transport symmetry but ignore it.
            del client_ip
        metadata = self._get_oidc_metadata(correlation_id=cid)
        try:
            return self._bootstrap_connector_session_with_httpx(
                username=username,
                password=password,
                correlation_id=cid,
                metadata=metadata,
            )
        except IaaiWafError as exc:
            if self._should_use_browser_fallback(exc):
                logger.warning(
                    "iaai_client.bootstrap.browser_fallback",
                    extra=make_log_extra(
                        "iaai_client.bootstrap.browser_fallback",
                        correlation_id=cid,
                        step=(exc.diagnostics.step if exc.diagnostics else None),
                        hint=(exc.diagnostics.hint if exc.diagnostics else None),
                    ),
                )
                return self._bootstrap_connector_session_with_browser(
                    username=username,
                    password=password,
                    correlation_id=cid,
                    metadata=metadata,
                )
            raise

    def _bootstrap_connector_session_with_httpx(
        self,
        *,
        username: str,
        password: str,
        correlation_id: str,
        metadata: dict[str, Any],
    ) -> IaaiConnectorBootstrapResult:
        code_verifier = _generate_code_verifier()
        authorize_params = self._build_authorize_params(code_verifier)
        authorize_response = self._request_browser_step(
            STEP_AUTHORIZE,
            correlation_id=correlation_id,
            callback=lambda: self._client.get(
                metadata["authorization_endpoint"],
                params=authorize_params,
                headers=self._build_browser_document_headers(referer=None, same_origin=False),
            ),
        )
        login_url = _resolve_location_url(authorize_response, authorize_response.headers.get("location"))
        login_page = self._request_browser_step(
            STEP_LOGIN_PAGE,
            correlation_id=correlation_id,
            callback=lambda: self._client.get(
                login_url,
                headers=self._build_browser_document_headers(referer=None, same_origin=False),
            ),
        )
        self._run_imperva_preflight(login_page=login_page, correlation_id=correlation_id)
        csrf_token = _extract_request_verification_token(login_page.text)
        if not csrf_token:
            raise IaaiConfigurationError(
                "IAAI login page token is missing.",
                diagnostics=self._make_diagnostics(
                    correlation_id=correlation_id,
                    step=STEP_LOGIN_PAGE,
                    error_code="configuration_error",
                    failure_class="configuration_error",
                    hint="missing_request_verification_token",
                ),
            )
        login_response = self._request_browser_step(
            STEP_LOGIN_SUBMIT,
            correlation_id=correlation_id,
            callback=lambda: self._client.post(
                str(login_page.request.url),
                data={
                    "Input.Email": username,
                    "Input.Password": password,
                    "Input.RememberMe": "false",
                    "__RequestVerificationToken": csrf_token,
                },
                headers=self._build_browser_form_headers(referer=str(login_page.request.url)),
            ),
        )
        code = self._resolve_authorization_code(
            login_response,
            referer=str(login_page.request.url),
            correlation_id=correlation_id,
        )
        if not code:
            raise IaaiAuthenticationError(
                "IAAI credentials were rejected.",
                diagnostics=self._make_diagnostics(
                    correlation_id=correlation_id,
                    step=STEP_LOGIN_SUBMIT,
                    error_code="invalid_credentials",
                    failure_class="auth_rejected",
                    hint=INVALID_CREDENTIALS_HINT,
                ),
            )
        token_payload = self._exchange_code_for_tokens(
            metadata["token_endpoint"],
            code=code,
            code_verifier=code_verifier,
            correlation_id=correlation_id,
        )
        session_bundle = self._build_session_bundle(username=username, token_payload=token_payload)
        encrypted_bundle = self._serialize_bundle(session_bundle)
        return IaaiConnectorBootstrapResult(
            bundle=encrypted_bundle,
            account_label=session_bundle.account_label,
            connection_status=self._connection_status_for_bundle(session_bundle),
            verified_at=datetime.now(timezone.utc),
        )

    def _bootstrap_connector_session_with_browser(
        self,
        *,
        username: str,
        password: str,
        correlation_id: str,
        metadata: dict[str, Any],
    ) -> IaaiConnectorBootstrapResult:
        code_verifier = _generate_code_verifier()
        authorize_params = self._build_authorize_params(code_verifier)
        authorize_url = str(httpx.URL(metadata["authorization_endpoint"]).copy_merge_params(authorize_params))
        timeout_ms = int(self._settings.iaai_browser_bootstrap_timeout_seconds * 1000)
        browser_cookies: list[dict[str, Any]] = []
        callback_code: str | None = None
        try:
            from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
            from playwright.sync_api import sync_playwright
        except Exception as exc:  # pragma: no cover - exercised only when runtime is missing browser deps
            raise IaaiConfigurationError(
                "IAAI browser bootstrap dependencies are unavailable.",
                diagnostics=self._make_diagnostics(
                    correlation_id=correlation_id,
                    step=STEP_IMPERVA_PREFLIGHT,
                    error_code="configuration_error",
                    failure_class="configuration_error",
                    hint="playwright_unavailable",
                ),
            ) from exc

        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=self._settings.iaai_browser_bootstrap_headless)
                context = browser.new_context(
                    user_agent=_browser_user_agent(),
                    locale=self._settings.iaai_mobile_language,
                    extra_http_headers={"Accept-Language": f"{self._settings.iaai_mobile_language},en;q=0.9"},
                )
                page = context.new_page()

                def capture_response(response) -> None:
                    nonlocal callback_code
                    location = response.headers.get("location") or ""
                    if callback_code is None:
                        callback_code = _extract_code_from_callback(location)

                page.on("response", capture_response)
                page.goto(authorize_url, wait_until="domcontentloaded", timeout=timeout_ms)
                page.wait_for_selector('input[name="Input.Email"]', timeout=timeout_ms)
                page.locator('input[name="Input.Email"]').fill(username)
                page.locator('input[name="Input.Password"]').fill(password)
                page.locator('button[type="submit"]').click(timeout=timeout_ms)
                page.wait_for_timeout(4000)
                if callback_code is None:
                    callback_code = _extract_code_from_callback(page.url)
                browser_cookies = context.cookies()
                browser.close()
        except PlaywrightTimeoutError as exc:
            raise IaaiWafError(
                "IAAI browser bootstrap timed out before authorization callback.",
                diagnostics=self._make_diagnostics(
                    correlation_id=correlation_id,
                    step=STEP_AUTHORIZE_CALLBACK,
                    error_code="upstream_rejected",
                    failure_class="browser_timeout",
                    hint="playwright_timeout",
                ),
            ) from exc

        if not callback_code:
            raise IaaiWafError(
                "IAAI browser bootstrap did not reach the authorization callback.",
                diagnostics=self._make_diagnostics(
                    correlation_id=correlation_id,
                    step=STEP_AUTHORIZE_CALLBACK,
                    error_code="upstream_rejected",
                    failure_class="browser_callback_missing",
                    hint="playwright_missing_callback_code",
                ),
            )

        self._import_browser_cookies(browser_cookies)
        logger.info(
            "iaai_client.bootstrap.browser_success",
            extra=make_log_extra(
                "iaai_client.bootstrap.browser_success",
                correlation_id=correlation_id,
                step=STEP_AUTHORIZE_CALLBACK,
                cookie_names=self._cookie_names(),
            ),
        )
        token_payload = self._exchange_code_for_tokens(
            metadata["token_endpoint"],
            code=callback_code,
            code_verifier=code_verifier,
            correlation_id=correlation_id,
        )
        session_bundle = self._build_session_bundle(username=username, token_payload=token_payload)
        encrypted_bundle = self._serialize_bundle(session_bundle)
        return IaaiConnectorBootstrapResult(
            bundle=encrypted_bundle,
            account_label=session_bundle.account_label,
            connection_status=self._connection_status_for_bundle(session_bundle),
            verified_at=datetime.now(timezone.utc),
        )

    def verify_connector_session(self, bundle: object) -> IaaiConnectorExecutionResult:
        if self._gateway_enabled:
            response = self._request_gateway_json(
                "POST",
                GATEWAY_CONNECTOR_VERIFY_PATH,
                json={"session_bundle": _require_encrypted_bundle(bundle).to_payload()},
            )
            return _parse_connector_execution_response(response.payload or {}, etag=response.etag, not_modified=response.not_modified)
        session_bundle = self._require_bundle(bundle)
        refreshed_bundle = self._ensure_fresh_access_token(session_bundle)
        return IaaiConnectorExecutionResult(
            payload=None,
            bundle=self._serialize_bundle(refreshed_bundle),
            etag=None,
            not_modified=False,
            connection_status=self._connection_status_for_bundle(refreshed_bundle),
            verified_at=datetime.now(timezone.utc),
            used_at=datetime.now(timezone.utc),
        )

    def search(self, payload: dict) -> dict:
        response = self.search_with_metadata(payload)
        if response.payload is None:
            raise RuntimeError("IAAI search payload is not available.")
        return response.payload

    def search_with_metadata(self, payload: dict, etag: str | None = None) -> IaaiHttpPayloadResponse:
        if self._gateway_enabled:
            return self._request_gateway_json("POST", GATEWAY_SEARCH_PATH, json=payload, etag=etag)
        response = self._client.post(self._settings.iaai_mobile_search_path, json=payload, headers=self._build_public_headers(etag=etag))
        return self._response_to_payload(response)

    def lot_details_with_metadata(self, provider_lot_id: str, etag: str | None = None) -> IaaiHttpPayloadResponse:
        if self._gateway_enabled:
            return self._request_gateway_json(
                "POST",
                GATEWAY_LOT_DETAILS_PATH,
                json={"provider_lot_id": provider_lot_id},
                etag=etag,
            )
        response = self._client.get(
            self._settings.iaai_mobile_inventory_details_path.format(provider_lot_id=provider_lot_id),
            headers=self._build_public_headers(etag=etag),
        )
        return self._response_to_payload(response)

    def search_with_connector_session(self, payload: dict, bundle: object) -> IaaiConnectorExecutionResult:
        if self._gateway_enabled:
            response = self._request_gateway_json(
                "POST",
                GATEWAY_CONNECTOR_EXECUTE_SEARCH_PATH,
                json={"session_bundle": _require_encrypted_bundle(bundle).to_payload(), "search_payload": payload},
            )
            return _parse_connector_execution_response(response.payload or {}, etag=response.etag, not_modified=response.not_modified)
        return self._execute_with_connector_bundle(
            bundle,
            lambda session_bundle: self._client.post(
                self._settings.iaai_mobile_search_path,
                json=payload,
                headers=self._build_authenticated_headers(session_bundle),
            ),
        )

    def lot_details_with_connector_session(
        self,
        provider_lot_id: str,
        bundle: object,
        etag: str | None = None,
    ) -> IaaiConnectorExecutionResult:
        if self._gateway_enabled:
            response = self._request_gateway_json(
                "POST",
                GATEWAY_CONNECTOR_EXECUTE_LOT_DETAILS_PATH,
                json={
                    "session_bundle": _require_encrypted_bundle(bundle).to_payload(),
                    "provider_lot_id": provider_lot_id,
                },
                etag=etag,
            )
            return _parse_connector_execution_response(response.payload or {}, etag=response.etag, not_modified=response.not_modified)
        return self._execute_with_connector_bundle(
            bundle,
            lambda session_bundle: self._client.get(
                self._settings.iaai_mobile_inventory_details_path.format(provider_lot_id=provider_lot_id),
                headers=self._build_authenticated_headers(session_bundle, etag=etag),
            ),
        )

    def close(self) -> None:
        self._client.close()

    def _request_gateway_json(
        self,
        method: str,
        path: str,
        *,
        json: Optional[dict] = None,
        etag: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> IaaiHttpPayloadResponse:
        headers: dict[str, str] = {}
        if etag:
            headers["If-None-Match"] = etag
        if correlation_id:
            headers[REQUEST_CORRELATION_ID_HEADER] = correlation_id
        try:
            response = self._client.request(method, path, json=json, headers=headers)
        except httpx.HTTPError as exc:
            raise IaaiGatewayUnavailableError(
                "IAAI gateway is unavailable.",
                diagnostics=self._make_diagnostics(
                    correlation_id=correlation_id,
                    step=None,
                    error_code="unavailable",
                    failure_class="transport_error",
                    hint=type(exc).__name__,
                ),
            ) from exc
        if response.status_code == httpx.codes.NOT_MODIFIED:
            return IaaiHttpPayloadResponse(payload=None, etag=response.headers.get("etag") or etag, not_modified=True)
        if response.is_error:
            self._raise_gateway_error(response)
        try:
            payload = response.json()
        except ValueError as exc:
            raise IaaiGatewayMalformedResponseError("IAAI gateway returned invalid JSON.") from exc
        if not isinstance(payload, dict):
            raise IaaiGatewayMalformedResponseError("IAAI gateway response must be a JSON object.")
        return IaaiHttpPayloadResponse(payload=payload, etag=response.headers.get("etag"), not_modified=False)

    @staticmethod
    def _raise_gateway_error(response: httpx.Response) -> None:
        gateway_error = (response.headers.get(GATEWAY_ERROR_HEADER) or "").strip().lower()
        diagnostics = _extract_gateway_diagnostics(response)
        if gateway_error == "upstream_rejected":
            raise IaaiWafError("IAAI rejected connector bootstrap request.", diagnostics=diagnostics)
        if gateway_error == "invalid_credentials":
            raise IaaiAuthenticationError("IAAI credentials were rejected.", diagnostics=diagnostics)
        if gateway_error == "auth_invalid":
            raise IaaiSessionInvalidError("IAAI session is no longer valid.", diagnostics=diagnostics)
        if gateway_error == "malformed_response":
            raise IaaiGatewayMalformedResponseError("IAAI gateway returned a malformed upstream response.", diagnostics=diagnostics)
        if gateway_error == "unavailable":
            raise IaaiGatewayUnavailableError("IAAI gateway is unavailable.", diagnostics=diagnostics)
        raise IaaiConfigurationError(
            f"IAAI gateway request failed with status {response.status_code}.",
            diagnostics=diagnostics,
        )

    def _execute_with_connector_bundle(self, bundle: object, callback) -> IaaiConnectorExecutionResult:
        session_bundle = self._ensure_fresh_access_token(self._require_bundle(bundle))
        response = callback(session_bundle)
        if response.status_code in {401, 403}:
            if session_bundle.refresh_token:
                try:
                    session_bundle = self._refresh_session_bundle(session_bundle)
                except IaaiRefreshError as exc:
                    raise IaaiSessionInvalidError(str(exc)) from exc
                response = callback(session_bundle)
            if response.status_code in {401, 403}:
                raise IaaiSessionInvalidError("IAAI session was rejected upstream.")
        payload_response = self._response_to_payload(response)
        return IaaiConnectorExecutionResult(
            payload=payload_response.payload,
            bundle=self._serialize_bundle(session_bundle),
            etag=payload_response.etag,
            not_modified=payload_response.not_modified,
            connection_status=self._connection_status_for_bundle(session_bundle),
            verified_at=datetime.now(timezone.utc),
            used_at=datetime.now(timezone.utc),
        )

    def _get_oidc_metadata(self, *, correlation_id: str) -> dict[str, Any]:
        response = self._request_browser_step(
            STEP_OIDC_METADATA,
            correlation_id=correlation_id,
            callback=lambda: self._client.get(self._settings.iaai_oidc_configuration_path),
        )
        payload = response.json()
        if not isinstance(payload, dict):
            raise IaaiConfigurationError(
                "IAAI OIDC metadata is invalid.",
                diagnostics=self._make_diagnostics(
                    correlation_id=correlation_id,
                    step=STEP_OIDC_METADATA,
                    error_code="malformed_response",
                    failure_class="malformed_response",
                ),
            )
        return payload

    def _build_authorize_params(self, code_verifier: str) -> dict[str, str]:
        return {
            "state": uuid4().hex,
            "theme": "light",
            "acr_values": "persistent-cookie",
            "response_type": "code",
            "nonce": uuid4().hex,
            "code_challenge_method": "S256",
            "scope": OIDC_SCOPE,
            "cultur": self._settings.iaai_mobile_language,
            "code_challenge": _build_code_challenge(code_verifier),
            "redirect_uri": self._settings.iaai_oidc_redirect_uri,
            "lang": self._settings.iaai_mobile_language,
            "client_id": self._settings.iaai_oidc_client_id,
            "responseType": "id_token",
        }

    def _exchange_code_for_tokens(
        self,
        token_endpoint: str,
        *,
        code: str,
        code_verifier: str,
        correlation_id: str,
    ) -> dict[str, Any]:
        response = self._request_browser_step(
            STEP_TOKEN_EXCHANGE,
            correlation_id=correlation_id,
            callback=lambda: self._client.post(
                token_endpoint,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": self._settings.iaai_oidc_redirect_uri,
                    "client_id": self._settings.iaai_oidc_client_id,
                    "code_verifier": code_verifier,
                },
                headers={
                    "Accept": "*/*",
                    "Accept-Language": f"{self._settings.iaai_mobile_language},en;q=0.9",
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "User-Agent": self._settings.iaai_mobile_user_agent,
                },
            ),
        )
        if response.status_code in {400, 401}:
            raise IaaiAuthenticationError(
                "IAAI token exchange rejected the provided credentials.",
                diagnostics=self._make_diagnostics(
                    correlation_id=correlation_id,
                    step=STEP_TOKEN_EXCHANGE,
                    error_code="invalid_credentials",
                    failure_class="auth_rejected",
                    upstream_status_code=response.status_code,
                ),
            )
        payload = response.json()
        if not isinstance(payload, dict) or not payload.get("access_token"):
            raise IaaiConfigurationError(
                "IAAI token response is invalid.",
                diagnostics=self._make_diagnostics(
                    correlation_id=correlation_id,
                    step=STEP_TOKEN_EXCHANGE,
                    error_code="malformed_response",
                    failure_class="malformed_response",
                ),
            )
        return payload

    def _refresh_token(self, refresh_token: str) -> dict[str, Any]:
        response = self._client.post(
            self._settings.iaai_oidc_token_path,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": self._settings.iaai_oidc_client_id,
            },
        )
        if response.status_code in {400, 401}:
            raise IaaiRefreshError("IAAI refresh token is no longer valid.")
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or not payload.get("access_token"):
            raise IaaiRefreshError("IAAI refresh response is invalid.")
        return payload

    def _build_session_bundle(self, *, username: str, token_payload: dict[str, Any]) -> IaaiSessionBundle:
        expires_in = token_payload.get("expires_in")
        expires_at = None
        if expires_in is not None:
            try:
                expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
            except (TypeError, ValueError):
                expires_at = None
        header_profile = IaaiHeaderProfile(
            tenant=self._settings.iaai_mobile_tenant,
            apikey=self._settings.iaai_mobile_apikey,
            deviceid=str(uuid4()).upper(),
            request_type=self._settings.iaai_mobile_request_type,
            app_version=self._settings.iaai_mobile_app_version,
            country=self._settings.iaai_mobile_country,
            language=self._settings.iaai_mobile_language,
            user_agent=self._settings.iaai_mobile_user_agent,
            device_type="IOS",
            os_version="26.4",
            model_name="iPhone 15 Plus",
            session_id=_new_mobile_session_id(),
        )
        user_id = _extract_user_id_from_access_token(str(token_payload["access_token"]))
        return IaaiSessionBundle(
            access_token=str(token_payload["access_token"]),
            refresh_token=(str(token_payload["refresh_token"]) if token_payload.get("refresh_token") else None),
            expires_at=expires_at,
            account_label=username,
            user_id=user_id,
            cookies=tuple(sorted((cookie.name, cookie.value) for cookie in self._client.cookies.jar)),
            header_profile=header_profile,
            captured_at=datetime.now(timezone.utc),
        )

    def _ensure_fresh_access_token(self, bundle: IaaiSessionBundle) -> IaaiSessionBundle:
        self._validate_session_bundle(bundle)
        if bundle.expires_at is None or bundle.expires_at > datetime.now(timezone.utc) + timedelta(minutes=1):
            return bundle
        if not bundle.refresh_token:
            raise IaaiSessionInvalidError("IAAI access token expired and no refresh token is stored.")
        return self._refresh_session_bundle(bundle)

    def _refresh_session_bundle(self, bundle: IaaiSessionBundle) -> IaaiSessionBundle:
        token_payload = self._refresh_token(bundle.refresh_token or "")
        refreshed = self._build_session_bundle(username=bundle.account_label or "", token_payload=token_payload)
        return IaaiSessionBundle(
            access_token=refreshed.access_token,
            refresh_token=refreshed.refresh_token or bundle.refresh_token,
            expires_at=refreshed.expires_at,
            account_label=bundle.account_label,
            user_id=refreshed.user_id or bundle.user_id,
            cookies=tuple(sorted((cookie.name, cookie.value) for cookie in self._client.cookies.jar)) or bundle.cookies,
            header_profile=IaaiHeaderProfile(
                tenant=bundle.header_profile.tenant,
                apikey=bundle.header_profile.apikey,
                deviceid=bundle.header_profile.deviceid,
                request_type=bundle.header_profile.request_type,
                app_version=bundle.header_profile.app_version,
                country=bundle.header_profile.country,
                language=bundle.header_profile.language,
                user_agent=bundle.header_profile.user_agent,
                device_type=bundle.header_profile.device_type,
                os_version=bundle.header_profile.os_version,
                model_name=bundle.header_profile.model_name,
                session_id=bundle.header_profile.session_id,
            ),
            captured_at=datetime.now(timezone.utc),
        )

    def _build_public_headers(self, *, etag: str | None = None) -> dict[str, str]:
        headers = {"Accept": "application/json, text/plain, */*"}
        if etag:
            headers["If-None-Match"] = etag
        return headers

    def _build_authenticated_headers(self, bundle: IaaiSessionBundle, *, etag: str | None = None) -> dict[str, str]:
        headers = bundle.header_profile.to_headers(
            access_token=bundle.access_token,
            user_id=bundle.user_id,
            extra_cookies=bundle.cookies,
        )
        if etag:
            headers["If-None-Match"] = etag
        return headers

    def _response_to_payload(self, response: httpx.Response) -> IaaiHttpPayloadResponse:
        if response.status_code == 304:
            return IaaiHttpPayloadResponse(payload=None, etag=response.headers.get("etag"), not_modified=True)
        if response.status_code == 403 and _looks_like_waf_page(response.text):
            raise IaaiWafError("IAAI upstream rejected the request with an Imperva/WAF page.")
        response.raise_for_status()
        payload = response.json() if response.content else None
        return IaaiHttpPayloadResponse(payload=payload, etag=response.headers.get("etag"), not_modified=False)

    def _connection_status_for_bundle(self, bundle: IaaiSessionBundle) -> str:
        if bundle.expires_at is None:
            return "connected"
        threshold = datetime.now(timezone.utc) + timedelta(minutes=self._settings.iaai_connector_session_expiring_threshold_minutes)
        return "expiring" if bundle.expires_at <= threshold else "connected"

    def _serialize_bundle(self, bundle: IaaiSessionBundle) -> IaaiEncryptedSessionBundle:
        raw = json.dumps(bundle.to_payload(), separators=(",", ":")).encode("utf-8")
        encoded = base64.urlsafe_b64encode(raw).decode("ascii")
        return IaaiEncryptedSessionBundle(
            encrypted_bundle=encoded,
            key_version=self._settings.iaai_connector_encryption_key_version,
            captured_at=bundle.captured_at,
            expires_at=bundle.expires_at,
        )

    def _require_bundle(self, bundle: object) -> IaaiSessionBundle:
        if isinstance(bundle, IaaiEncryptedSessionBundle):
            raw = base64.urlsafe_b64decode(bundle.encrypted_bundle.encode("ascii")).decode("utf-8")
            resolved = IaaiSessionBundle.from_payload(json.loads(raw))
            self._validate_session_bundle(resolved)
            return resolved
        if isinstance(bundle, IaaiSessionBundle):
            self._validate_session_bundle(bundle)
            return bundle
        raise IaaiConfigurationError("IAAI connector execution requires a serialized session bundle.")

    def _request_browser_step(
        self,
        step: str,
        *,
        correlation_id: str,
        callback,
    ) -> httpx.Response:
        try:
            response = callback()
        except httpx.TimeoutException as exc:
            raise IaaiGatewayUnavailableError(
                "IAAI upstream timed out.",
                diagnostics=self._make_diagnostics(
                    correlation_id=correlation_id,
                    step=step,
                    error_code="unavailable",
                    failure_class="timeout",
                    hint=REQUEST_TIMEOUT_HINT,
                ),
            ) from exc
        except httpx.HTTPError as exc:
            raise IaaiGatewayUnavailableError(
                "IAAI upstream is unavailable.",
                diagnostics=self._make_diagnostics(
                    correlation_id=correlation_id,
                    step=step,
                    error_code="unavailable",
                    failure_class="transport_error",
                    hint=type(exc).__name__,
                ),
            ) from exc
        if response.status_code in {401, 403} and _looks_like_waf_page(response.text):
            raise IaaiWafError(
                "IAAI login flow was blocked by Imperva.",
                diagnostics=self._make_diagnostics(
                    correlation_id=correlation_id,
                    step=step,
                    error_code="upstream_rejected",
                    failure_class="upstream_rejected",
                    upstream_status_code=response.status_code,
                    hint=WAF_HINT,
                ),
            )
        if response.status_code >= 500:
            raise IaaiGatewayUnavailableError(
                "IAAI upstream is unavailable.",
                diagnostics=self._make_diagnostics(
                    correlation_id=correlation_id,
                    step=step,
                    error_code="unavailable",
                    failure_class="upstream_error",
                    upstream_status_code=response.status_code,
                ),
            )
        return response

    def _run_imperva_preflight(self, *, login_page: httpx.Response, correlation_id: str) -> None:
        script_path = _extract_imperva_script_path(login_page.text)
        self._log_cookie_state(
            correlation_id=correlation_id,
            step=STEP_LOGIN_PAGE,
            reason="after_login_page",
            response=login_page,
        )
        if not script_path:
            raise IaaiWafError(
                "IAAI login page is missing the Imperva preflight script.",
                diagnostics=self._make_diagnostics(
                    correlation_id=correlation_id,
                    step=STEP_IMPERVA_PREFLIGHT,
                    error_code="upstream_rejected",
                    failure_class="bootstrap_incomplete",
                    hint="missing_imperva_script",
                ),
            )
        script_response = self._request_browser_step(
            STEP_IMPERVA_PREFLIGHT,
            correlation_id=correlation_id,
            callback=lambda: self._client.get(
                urljoin(str(login_page.request.url), script_path),
                headers=self._build_browser_script_headers(referer=str(login_page.request.url)),
            ),
        )
        self._log_cookie_state(
            correlation_id=correlation_id,
            step=STEP_IMPERVA_PREFLIGHT,
            reason="after_script_get",
            response=script_response,
        )
        imperva_token = self._cookie_value(IMPERVA_COOKIE_NAME)
        token_source = "cookie"
        if not imperva_token:
            imperva_token = _extract_imperva_token_from_script_body(script_response.text)
            if imperva_token:
                token_source = "script_body"
                logger.info(
                    "iaai_client.bootstrap.imperva_token_fallback",
                    extra=make_log_extra(
                        "iaai_client.bootstrap.imperva_token_fallback",
                        correlation_id=correlation_id,
                        step=STEP_IMPERVA_PREFLIGHT,
                        token_source=token_source,
                        script_content_type=script_response.headers.get("content-type"),
                        script_body_length=len(script_response.text or ""),
                    ),
                )
        if not imperva_token:
            self._log_cookie_state(
                correlation_id=correlation_id,
                step=STEP_IMPERVA_PREFLIGHT,
                reason="missing_imperva_token",
                response=script_response,
            )
            raise IaaiWafError(
                "IAAI Imperva preflight state is incomplete.",
                diagnostics=self._make_diagnostics(
                    correlation_id=correlation_id,
                    step=STEP_IMPERVA_PREFLIGHT,
                    error_code="upstream_rejected",
                    failure_class="bootstrap_incomplete",
                    hint="missing_reese84_cookie_after_script_get",
                ),
            )
        preflight_response = self._request_browser_step(
            STEP_IMPERVA_PREFLIGHT,
            correlation_id=correlation_id,
            callback=lambda: self._client.post(
                urljoin(str(login_page.request.url), f"{script_path}?d={IMPERVA_SCRIPT_DOMAIN_PARAM}"),
                content=json.dumps(imperva_token).encode("utf-8"),
                headers=self._build_browser_preflight_headers(referer=str(login_page.request.url)),
            ),
        )
        self._log_cookie_state(
            correlation_id=correlation_id,
            step=STEP_IMPERVA_PREFLIGHT,
            reason="after_script_post",
            response=preflight_response,
            token_source=token_source,
        )
        if preflight_response.is_error:
            raise IaaiWafError(
                "IAAI Imperva preflight was rejected.",
                diagnostics=self._make_diagnostics(
                    correlation_id=correlation_id,
                    step=STEP_IMPERVA_PREFLIGHT,
                    error_code="upstream_rejected",
                    failure_class="upstream_rejected",
                    upstream_status_code=preflight_response.status_code,
                    hint=WAF_HINT,
                ),
            )
        if not self._cookie_value("nlbi_2831003_2147483392"):
            # Imperva rotates additional load-balancer cookies after the POST. Absence usually means the challenge
            # did not finish even if the endpoint returned 200.
            payload = _safe_json_dict(preflight_response)
            if not payload.get("token"):
                raise IaaiWafError(
                    "IAAI Imperva preflight did not return the expected anti-bot state.",
                    diagnostics=self._make_diagnostics(
                        correlation_id=correlation_id,
                        step=STEP_IMPERVA_PREFLIGHT,
                        error_code="upstream_rejected",
                        failure_class="bootstrap_incomplete",
                        hint="missing_imperva_post_state",
                    ),
                )

    def _log_cookie_state(
        self,
        *,
        correlation_id: str,
        step: str,
        reason: str,
        response: httpx.Response | None,
        token_source: str | None = None,
    ) -> None:
        cookie_names = self._cookie_names()
        logger.info(
            "iaai_client.bootstrap.state",
            extra=make_log_extra(
                "iaai_client.bootstrap.state",
                correlation_id=correlation_id,
                step=step,
                reason=reason,
                cookie_names=cookie_names,
                has_reese84=IMPERVA_COOKIE_NAME in cookie_names,
                has_request_verification_token=bool(
                    response is not None and _extract_request_verification_token(response.text or "")
                ),
                response_status=(response.status_code if response is not None else None),
                response_content_type=(response.headers.get("content-type") if response is not None else None),
                response_body_length=(len(response.text or "") if response is not None else None),
                response_set_cookie_names=(
                    _extract_set_cookie_names(response.headers) if response is not None else None
                ),
                token_source=token_source,
            ),
        )

    def _resolve_authorization_code(
        self,
        response: httpx.Response,
        *,
        referer: str,
        correlation_id: str,
    ) -> str | None:
        direct_code = _extract_code_from_callback(response.headers.get("location") or str(response.request.url))
        if direct_code:
            return direct_code
        callback_url = response.headers.get("location")
        if callback_url:
            resolved_callback_url = _resolve_location_url(response, callback_url)
            if "/connect/authorize/callback" in resolved_callback_url:
                callback_response = self._request_browser_step(
                    STEP_AUTHORIZE_CALLBACK,
                    correlation_id=correlation_id,
                    callback=lambda: self._client.get(
                        resolved_callback_url,
                        headers=self._build_browser_document_headers(referer=referer, same_origin=True),
                    ),
                )
                for candidate in (
                    callback_response.headers.get("location"),
                    str(callback_response.request.url),
                    str(callback_response.url),
                ):
                    callback_code = _extract_code_from_callback(candidate or "")
                    if callback_code:
                        return callback_code
                hidden_code = _extract_hidden_input_value(callback_response.text, "code")
                if hidden_code:
                    return hidden_code
                form_action = _extract_form_action(callback_response.text)
                if form_action:
                    return _extract_code_from_callback(form_action)
        hidden_code = _extract_hidden_input_value(response.text, "code")
        if hidden_code:
            return hidden_code
        form_action = _extract_form_action(response.text)
        if form_action:
            return _extract_code_from_callback(form_action)
        return None

    def _validate_session_bundle(self, bundle: IaaiSessionBundle) -> None:
        if not bundle.access_token:
            raise IaaiSessionInvalidError("IAAI session bundle is missing the access token.")
        if not bundle.header_profile.deviceid:
            raise IaaiSessionInvalidError("IAAI session bundle is missing the mobile device identifier.")
        if not bundle.cookies:
            raise IaaiSessionInvalidError("IAAI session bundle is missing anti-bot cookies.")
        if not any(name.startswith(AUTHENTICATED_COOKIE_PREFIXES) for name, _ in bundle.cookies):
            raise IaaiSessionInvalidError("IAAI session bundle is missing required Imperva cookies.")

    def _cookie_value(self, name: str) -> str | None:
        for cookie in self._client.cookies.jar:
            if cookie.name == name:
                return cookie.value
        return None

    def _cookie_names(self) -> list[str]:
        names = {cookie.name for cookie in self._client.cookies.jar}
        return sorted(names)

    def _import_browser_cookies(self, cookies: list[dict[str, Any]]) -> None:
        for item in cookies:
            name = str(item.get("name") or "").strip()
            value = str(item.get("value") or "")
            if not name:
                continue
            self._client.cookies.set(
                name,
                value,
                domain=(str(item.get("domain")) if item.get("domain") else None),
                path=(str(item.get("path")) if item.get("path") else "/"),
            )

    def _build_browser_document_headers(self, *, referer: str | None, same_origin: bool) -> dict[str, str]:
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": f"{self._settings.iaai_mobile_language},en;q=0.9",
            "User-Agent": _browser_user_agent(),
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin" if same_origin else "none",
        }
        if referer:
            headers["Referer"] = referer
        return headers

    def _build_browser_script_headers(self, *, referer: str) -> dict[str, str]:
        return {
            "Accept": "*/*",
            "Accept-Language": f"{self._settings.iaai_mobile_language},en;q=0.9",
            "Referer": referer,
            "Sec-Fetch-Dest": "script",
            "Sec-Fetch-Mode": "no-cors",
            "Sec-Fetch-Site": "same-origin",
            "User-Agent": _browser_user_agent(),
        }

    def _build_browser_preflight_headers(self, *, referer: str) -> dict[str, str]:
        return {
            "Accept": "application/json; charset=utf-8",
            "Accept-Language": f"{self._settings.iaai_mobile_language},en;q=0.9",
            "Content-Type": "text/plain; charset=utf-8",
            "Origin": "https://login.iaai.com",
            "Referer": referer,
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "User-Agent": _browser_user_agent(),
        }

    def _build_browser_form_headers(self, *, referer: str) -> dict[str, str]:
        return {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": f"{self._settings.iaai_mobile_language},en;q=0.9",
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": "https://login.iaai.com",
            "Referer": referer,
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "User-Agent": _browser_user_agent(),
        }

    def _should_use_browser_fallback(self, exc: IaaiWafError) -> bool:
        diagnostics = exc.diagnostics
        if not self._settings.iaai_browser_bootstrap_enabled:
            return False
        if diagnostics is None:
            return False
        if diagnostics.step != STEP_IMPERVA_PREFLIGHT:
            return False
        return (diagnostics.hint or "") in BROWSER_FALLBACK_HINTS

    @staticmethod
    def _make_diagnostics(
        *,
        correlation_id: str | None,
        step: str | None,
        error_code: str | None,
        failure_class: str | None,
        upstream_status_code: int | None = None,
        hint: str | None = None,
    ) -> IaaiDiagnostics:
        return IaaiDiagnostics(
            correlation_id=correlation_id,
            step=step,
            error_code=error_code,
            failure_class=failure_class,
            upstream_status_code=upstream_status_code,
            hint=hint,
        )


def _parse_optional_datetime(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _generate_code_verifier() -> str:
    return base64.urlsafe_b64encode(uuid4().bytes + uuid4().bytes).decode("ascii").rstrip("=")


def _build_code_challenge(code_verifier: str) -> str:
    digest = sha256(code_verifier.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def _extract_request_verification_token(html: str) -> str | None:
    marker = 'name="__RequestVerificationToken" type="hidden" value="'
    if marker not in html:
        return None
    return html.split(marker, 1)[1].split('"', 1)[0]


def _extract_imperva_script_path(html: str) -> str | None:
    match = re.search(r'<script[^>]+src="([^"]*A-would-they-here-beathe-and-should-mis-fore-Cas[^"]*)"', html)
    if not match:
        return None
    return match.group(1)


def _extract_imperva_token_from_script_body(body: str) -> str | None:
    if not body:
        return None
    patterns = (
        r'"token"\s*:\s*"([^"]+)"',
        r"reese84\s*[:=]\s*['\"]([^'\"]+)['\"]",
        r"['\"](3:[^'\"]+)['\"]",
    )
    for pattern in patterns:
        match = re.search(pattern, body)
        if match:
            return match.group(1)
    return None


def _extract_hidden_input_value(html: str, name: str) -> str | None:
    pattern = rf'<input[^>]+name="{re.escape(name)}"[^>]+value="([^"]*)"'
    match = re.search(pattern, html)
    if match:
        return match.group(1)
    reverse_pattern = rf'<input[^>]+value="([^"]*)"[^>]+name="{re.escape(name)}"'
    reverse_match = re.search(reverse_pattern, html)
    if reverse_match:
        return reverse_match.group(1)
    return None


def _extract_form_action(html: str) -> str | None:
    match = re.search(r"<form[^>]+action=\"([^\"]+)\"", html)
    if not match:
        return None
    return match.group(1)


def _extract_code_from_callback(callback_url: str) -> str | None:
    parsed = urlparse(callback_url)
    query = parse_qs(parsed.query)
    values = query.get("code")
    if values:
        return values[0]
    if "code=" not in callback_url:
        return None
    trailing_query = callback_url.split("?", 1)[-1]
    fallback_values = parse_qs(trailing_query).get("code")
    return fallback_values[0] if fallback_values else None


def _looks_like_waf_page(body: str) -> bool:
    lowered = body.lower()
    return "imperva" in lowered or "/a-would-they-here-beathe" in lowered


def _extract_gateway_diagnostics(response: httpx.Response) -> IaaiDiagnostics | None:
    payload_diagnostics: IaaiDiagnostics | None = None
    try:
        payload = response.json()
    except ValueError:
        payload = None
    if isinstance(payload, dict):
        payload_diagnostics = IaaiDiagnostics.from_payload(payload.get("diagnostics"))
    upstream_status = response.headers.get(GATEWAY_UPSTREAM_STATUS_HEADER)
    parsed_upstream_status: int | None = None
    if upstream_status:
        try:
            parsed_upstream_status = int(upstream_status)
        except (TypeError, ValueError):
            parsed_upstream_status = None
    base = payload_diagnostics or IaaiDiagnostics()
    return IaaiDiagnostics(
        correlation_id=base.correlation_id or response.headers.get(GATEWAY_CORRELATION_ID_HEADER),
        step=base.step or response.headers.get(GATEWAY_STEP_HEADER),
        error_code=base.error_code or response.headers.get(GATEWAY_ERROR_HEADER),
        failure_class=base.failure_class or response.headers.get(GATEWAY_FAILURE_CLASS_HEADER),
        upstream_status_code=base.upstream_status_code if base.upstream_status_code is not None else parsed_upstream_status,
        hint=base.hint,
    )


def _require_encrypted_bundle(bundle: object) -> IaaiEncryptedSessionBundle:
    if isinstance(bundle, IaaiEncryptedSessionBundle):
        return bundle
    raise IaaiConfigurationError("IAAI gateway transport requires an encrypted session bundle.")


def _parse_connector_execution_response(
    payload: dict[str, Any],
    *,
    etag: str | None,
    not_modified: bool,
) -> IaaiConnectorExecutionResult:
    serialized_bundle = payload.get("session_bundle")
    bundle = None
    if isinstance(serialized_bundle, dict):
        bundle = IaaiEncryptedSessionBundle.from_payload(serialized_bundle)
    return IaaiConnectorExecutionResult(
        payload=payload.get("payload") if isinstance(payload.get("payload"), dict) else None,
        bundle=bundle,
        etag=etag,
        not_modified=not_modified,
        connection_status=str(payload.get("status") or "connected"),
        verified_at=_parse_optional_datetime(payload.get("verified_at")),
        used_at=_parse_optional_datetime(payload.get("used_at")),
    )


def _extract_user_id_from_access_token(access_token: str) -> str | None:
    parts = access_token.split(".")
    if len(parts) < 2:
        return None
    padding = "=" * (-len(parts[1]) % 4)
    try:
        payload = json.loads(base64.urlsafe_b64decode(parts[1] + padding).decode("utf-8"))
    except Exception:
        return None
    for field_name in ("sub", "user_id", "nameid"):
        value = payload.get(field_name)
        if value:
            return str(value)
    return None


def _resolve_location_url(response: httpx.Response, location: str | None) -> str:
    if not location:
        return str(response.request.url)
    return str(response.request.url.join(location))


def _browser_user_agent() -> str:
    return (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Mobile/15E148 Safari/604.1"
    )


def _mobile_language_code(value: str) -> str:
    return value.split("-", 1)[0]


def _new_mobile_session_id() -> str:
    return str(int(datetime.now(timezone.utc).timestamp() * 1000))


def _safe_json_dict(response: httpx.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _extract_set_cookie_names(headers: httpx.Headers) -> list[str]:
    names: list[str] = []
    for value in headers.get_list("set-cookie"):
        candidate = value.split("=", 1)[0].strip()
        if candidate:
            names.append(candidate)
    return sorted(set(names))
