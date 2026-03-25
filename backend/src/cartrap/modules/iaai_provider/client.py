"""Direct IAAI connector client with OIDC bootstrap and refresh-token support."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import httpx

from cartrap.config import Settings, get_settings
from cartrap.modules.iaai_provider.errors import (
    IaaiAuthenticationError,
    IaaiConfigurationError,
    IaaiRefreshError,
    IaaiSessionInvalidError,
    IaaiWafError,
)


OIDC_SCOPE = "openid profile email offline_access BuyerProfileClaims"


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

    def to_headers(self, *, access_token: str, user_id: str | None, extra_cookies: tuple[tuple[str, str], ...]) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "tenant": self.tenant,
            "apikey": self.apikey,
            "deviceid": self.deviceid,
            "x-request-type": self.request_type,
            "x-app-version": self.app_version,
            "x-country": self.country,
            "x-language": self.language,
            "x-datetime": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "User-Agent": self.user_agent,
            "Accept": "application/json, text/plain, */*",
        }
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
    def __init__(self, settings: Optional[Settings] = None, client: Optional[httpx.Client] = None) -> None:
        self._settings = settings or get_settings()
        self._client = client or httpx.Client(
            follow_redirects=False,
            timeout=httpx.Timeout(self._settings.iaai_http_timeout_seconds, connect=self._settings.iaai_http_connect_timeout_seconds),
            headers={"Accept-Language": self._settings.iaai_mobile_language, "User-Agent": self._settings.iaai_mobile_user_agent},
        )

    def bootstrap_connector_session(
        self,
        *,
        username: str,
        password: str,
        client_ip: str | None = None,
    ) -> IaaiConnectorBootstrapResult:
        del client_ip
        metadata = self._get_oidc_metadata()
        code_verifier = _generate_code_verifier()
        authorize_params = self._build_authorize_params(code_verifier)
        authorize_response = self._client.get(metadata["authorization_endpoint"], params=authorize_params)
        login_url = authorize_response.headers.get("location") or str(authorize_response.request.url)
        login_page = self._client.get(login_url)
        if _looks_like_waf_page(login_page.text):
            raise IaaiWafError("IAAI login flow was blocked by Imperva.")
        csrf_token = _extract_request_verification_token(login_page.text)
        if not csrf_token:
            raise IaaiConfigurationError("IAAI login page token is missing.")
        login_response = self._client.post(
            str(login_page.request.url),
            data={
                "Input.Email": username,
                "Input.Password": password,
                "Input.RememberMe": "false",
                "__RequestVerificationToken": csrf_token,
            },
        )
        callback_url = login_response.headers.get("location") or str(login_response.request.url)
        code = _extract_code_from_callback(callback_url)
        if not code:
            raise IaaiAuthenticationError("IAAI credentials were rejected.")
        token_payload = self._exchange_code_for_tokens(metadata["token_endpoint"], code=code, code_verifier=code_verifier)
        session_bundle = self._build_session_bundle(username=username, token_payload=token_payload)
        encrypted_bundle = self._serialize_bundle(session_bundle)
        return IaaiConnectorBootstrapResult(
            bundle=encrypted_bundle,
            account_label=session_bundle.account_label,
            connection_status=self._connection_status_for_bundle(session_bundle),
            verified_at=datetime.now(timezone.utc),
        )

    def verify_connector_session(self, bundle: object) -> IaaiConnectorExecutionResult:
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
        response = self._client.post(self._settings.iaai_mobile_search_path, json=payload, headers=self._build_public_headers(etag=etag))
        return self._response_to_payload(response)

    def lot_details_with_metadata(self, provider_lot_id: str, etag: str | None = None) -> IaaiHttpPayloadResponse:
        response = self._client.get(
            self._settings.iaai_mobile_inventory_details_path.format(provider_lot_id=provider_lot_id),
            headers=self._build_public_headers(etag=etag),
        )
        return self._response_to_payload(response)

    def search_with_connector_session(self, payload: dict, bundle: object) -> IaaiConnectorExecutionResult:
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
        return self._execute_with_connector_bundle(
            bundle,
            lambda session_bundle: self._client.get(
                self._settings.iaai_mobile_inventory_details_path.format(provider_lot_id=provider_lot_id),
                headers=self._build_authenticated_headers(session_bundle, etag=etag),
            ),
        )

    def close(self) -> None:
        self._client.close()

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

    def _get_oidc_metadata(self) -> dict[str, Any]:
        response = self._client.get(self._settings.iaai_oidc_configuration_path)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise IaaiConfigurationError("IAAI OIDC metadata is invalid.")
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

    def _exchange_code_for_tokens(self, token_endpoint: str, *, code: str, code_verifier: str) -> dict[str, Any]:
        response = self._client.post(
            token_endpoint,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self._settings.iaai_oidc_redirect_uri,
                "client_id": self._settings.iaai_oidc_client_id,
                "code_verifier": code_verifier,
            },
        )
        if response.status_code in {400, 401}:
            raise IaaiAuthenticationError("IAAI token exchange rejected the provided credentials.")
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or not payload.get("access_token"):
            raise IaaiConfigurationError("IAAI token response is invalid.")
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
            deviceid=uuid4().hex,
            request_type=self._settings.iaai_mobile_request_type,
            app_version=self._settings.iaai_mobile_app_version,
            country=self._settings.iaai_mobile_country,
            language=self._settings.iaai_mobile_language,
            user_agent=self._settings.iaai_mobile_user_agent,
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
            return IaaiSessionBundle.from_payload(json.loads(raw))
        if isinstance(bundle, IaaiSessionBundle):
            return bundle
        raise IaaiConfigurationError("IAAI connector execution requires a serialized session bundle.")


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


def _extract_code_from_callback(callback_url: str) -> str | None:
    parsed = urlparse(callback_url)
    query = parse_qs(parsed.query)
    values = query.get("code")
    return values[0] if values else None


def _looks_like_waf_page(body: str) -> bool:
    lowered = body.lower()
    return "imperva" in lowered or "/a-would-they-here-beathe" in lowered


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
