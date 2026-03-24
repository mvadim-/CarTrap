"""Application configuration."""

from __future__ import annotations

from functools import lru_cache
from typing import List, Optional

import httpx
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PRIVATE_NETWORK_CORS_REGEX = (
    r"^https?://("
    r"localhost|127\.0\.0\.1|"
    r"10(?:\.\d{1,3}){3}|"
    r"192\.168(?:\.\d{1,3}){2}|"
    r"172\.(1[6-9]|2\d|3[0-1])(?:\.\d{1,3}){2}"
    r")(?::\d+)?$"
)


class Settings(BaseSettings):
    """Typed settings loaded from the environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = Field(default="CarTrap API", min_length=1)
    environment: str = Field(default="development", min_length=1)
    api_prefix: str = Field(default="/api", min_length=1)
    log_level: str = Field(default="INFO", min_length=1)
    backend_cors_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173,http://127.0.0.1:4173",
        alias="BACKEND_CORS_ORIGINS",
        min_length=1,
    )
    mongo_uri: str = Field(default="mongodb://localhost:27017", alias="MONGO_URI", min_length=1)
    mongo_db: str = Field(default="cartrap", alias="MONGO_DB", min_length=1)
    mongo_ping_on_startup: bool = Field(default=False, alias="MONGO_PING_ON_STARTUP")
    jwt_secret: str = Field(default="change-me", alias="JWT_SECRET", min_length=8)
    jwt_refresh_secret: str = Field(default="change-me-too", alias="JWT_REFRESH_SECRET", min_length=8)
    access_token_ttl_minutes: int = Field(default=30, alias="ACCESS_TOKEN_TTL_MINUTES", ge=1)
    refresh_token_ttl_minutes: int = Field(default=60 * 24 * 14, alias="REFRESH_TOKEN_TTL_MINUTES", ge=1)
    invite_ttl_hours: int = Field(default=72, alias="INVITE_TTL_HOURS", ge=1)
    saved_search_poll_interval_minutes: int = Field(default=15, alias="SAVED_SEARCH_POLL_INTERVAL_MINUTES", ge=1)
    watchlist_default_poll_interval_minutes: int = Field(
        default=15,
        alias="WATCHLIST_DEFAULT_POLL_INTERVAL_MINUTES",
        ge=1,
    )
    watchlist_near_auction_poll_interval_minutes: int = Field(
        default=1,
        alias="WATCHLIST_NEAR_AUCTION_POLL_INTERVAL_MINUTES",
        ge=1,
    )
    watchlist_near_auction_window_minutes: int = Field(
        default=120,
        alias="WATCHLIST_NEAR_AUCTION_WINDOW_MINUTES",
        ge=1,
    )
    bootstrap_admin_email: Optional[str] = Field(default=None, alias="BOOTSTRAP_ADMIN_EMAIL")
    bootstrap_admin_password: Optional[str] = Field(default=None, alias="BOOTSTRAP_ADMIN_PASSWORD")
    copart_api_base_url: str = Field(default="https://mmember.copart.com", alias="COPART_API_BASE_URL", min_length=1)
    copart_api_search_path: str = Field(default="/srch/?services=bidIncrementsBySiteV2", alias="COPART_API_SEARCH_PATH", min_length=1)
    copart_api_search_keywords_path: str = Field(
        default="/mcs/v2/public/data/search/keywords",
        alias="COPART_API_SEARCH_KEYWORDS_PATH",
        min_length=1,
    )
    copart_api_lot_details_path: str = Field(
        default="/lots-api/v1/lot-details?services=bidIncrementsBySiteV2",
        alias="COPART_API_LOT_DETAILS_PATH",
        min_length=1,
    )
    copart_api_device_name: Optional[str] = Field(default=None, alias="COPART_API_DEVICE_NAME")
    copart_api_d_token: Optional[str] = Field(default=None, alias="COPART_API_D_TOKEN")
    copart_api_cookie: Optional[str] = Field(default=None, alias="COPART_API_COOKIE")
    copart_api_site_code: str = Field(default="CPRTUS", alias="COPART_API_SITECODE", min_length=1)
    copart_connector_bootstrap_path: str = Field(default="/", alias="COPART_CONNECTOR_BOOTSTRAP_PATH", min_length=1)
    copart_connector_login_path: str = Field(
        default="/mds-api/v1/member/login",
        alias="COPART_CONNECTOR_LOGIN_PATH",
        min_length=1,
    )
    copart_connector_identity_path: Optional[str] = Field(
        default=None,
        alias="COPART_CONNECTOR_IDENTITY_PATH",
    )
    copart_connector_challenge_path: Optional[str] = Field(
        default="/mds-api/v1/member/challenge",
        alias="COPART_CONNECTOR_CHALLENGE_PATH",
    )
    copart_connector_verify_path: Optional[str] = Field(
        default="/mds-api/v1/member/me-info",
        alias="COPART_CONNECTOR_VERIFY_PATH",
    )
    copart_connector_encryption_key: Optional[str] = Field(default=None, alias="COPART_CONNECTOR_ENCRYPTION_KEY")
    copart_connector_encryption_key_version: str = Field(
        default="v1",
        alias="COPART_CONNECTOR_ENCRYPTION_KEY_VERSION",
        min_length=1,
    )
    copart_connector_session_expiring_threshold_minutes: int = Field(
        default=60,
        alias="COPART_CONNECTOR_SESSION_EXPIRING_THRESHOLD_MINUTES",
        ge=1,
    )
    copart_connector_mobile_company: str = Field(
        default="COPART",
        alias="COPART_CONNECTOR_MOBILE_COMPANY",
        min_length=1,
    )
    copart_connector_mobile_os: str = Field(
        default="ios",
        alias="COPART_CONNECTOR_MOBILE_OS",
        min_length=1,
    )
    copart_connector_mobile_language_code: str = Field(
        default="en-US",
        alias="COPART_CONNECTOR_MOBILE_LANGUAGE_CODE",
        min_length=1,
    )
    copart_connector_mobile_client_app_version: str = Field(
        default="6.7.2",
        alias="COPART_CONNECTOR_MOBILE_CLIENT_APP_VERSION",
        min_length=1,
    )
    copart_connector_mobile_user_agent: str = Field(
        default="MemberMobile/5 CFNetwork/3860.400.51 Darwin/25.3.0",
        alias="COPART_CONNECTOR_MOBILE_USER_AGENT",
        min_length=1,
    )
    copart_connector_mobile_ip_address: Optional[str] = Field(
        default=None,
        alias="COPART_CONNECTOR_MOBILE_IP_ADDRESS",
    )
    copart_connector_connect_rate_limit_attempts: int = Field(
        default=5,
        alias="COPART_CONNECTOR_CONNECT_RATE_LIMIT_ATTEMPTS",
        ge=1,
    )
    copart_connector_connect_rate_limit_window_seconds: int = Field(
        default=60,
        alias="COPART_CONNECTOR_CONNECT_RATE_LIMIT_WINDOW_SECONDS",
        ge=1,
    )
    copart_http_timeout_seconds: float = Field(default=15.0, alias="COPART_HTTP_TIMEOUT_SECONDS", gt=0)
    copart_http_connect_timeout_seconds: float = Field(default=5.0, alias="COPART_HTTP_CONNECT_TIMEOUT_SECONDS", gt=0)
    copart_http_keepalive_expiry_seconds: float = Field(
        default=30.0,
        alias="COPART_HTTP_KEEPALIVE_EXPIRY_SECONDS",
        gt=0,
    )
    copart_http_max_connections: int = Field(default=20, alias="COPART_HTTP_MAX_CONNECTIONS", ge=1)
    copart_http_max_keepalive_connections: int = Field(
        default=10,
        alias="COPART_HTTP_MAX_KEEPALIVE_CONNECTIONS",
        ge=1,
    )
    copart_gateway_base_url: Optional[str] = Field(default=None, alias="COPART_GATEWAY_BASE_URL")
    copart_gateway_token: Optional[str] = Field(default=None, alias="COPART_GATEWAY_TOKEN")
    copart_gateway_enable_gzip: bool = Field(default=True, alias="COPART_GATEWAY_ENABLE_GZIP")
    vapid_public_key: Optional[str] = Field(default=None, alias="VAPID_PUBLIC_KEY")
    vapid_private_key: Optional[str] = Field(default=None, alias="VAPID_PRIVATE_KEY")
    vapid_subject: Optional[str] = Field(default=None, alias="VAPID_SUBJECT")

    def __init__(self, **values):
        normalized_values = dict(values)
        for field_name, field_info in type(self).model_fields.items():
            alias = field_info.alias
            if alias and field_name in normalized_values and alias not in normalized_values:
                normalized_values[alias] = normalized_values.pop(field_name)
        super().__init__(**normalized_values)

    @property
    def cors_origins(self) -> List[str]:
        return [origin.strip() for origin in self.backend_cors_origins.split(",") if origin.strip()]

    @property
    def cors_origin_regex(self) -> Optional[str]:
        if self.environment.strip().lower() == "production":
            return None
        return PRIVATE_NETWORK_CORS_REGEX

    @property
    def copart_gateway_enabled(self) -> bool:
        return bool(self.copart_gateway_base_url)

    @model_validator(mode="after")
    def validate_copart_settings(self) -> "Settings":
        if self.copart_gateway_base_url:
            parsed_gateway_url = httpx.URL(self.copart_gateway_base_url)
            if parsed_gateway_url.scheme not in {"http", "https"}:
                raise ValueError("COPART_GATEWAY_BASE_URL must use http or https.")
            if not self.copart_gateway_token:
                raise ValueError("COPART_GATEWAY_TOKEN is required when COPART_GATEWAY_BASE_URL is set.")

        if self.copart_http_max_keepalive_connections > self.copart_http_max_connections:
            raise ValueError("COPART_HTTP_MAX_KEEPALIVE_CONNECTIONS cannot exceed COPART_HTTP_MAX_CONNECTIONS.")
        if self.copart_connector_encryption_key is not None and not self.copart_connector_encryption_key.strip():
            raise ValueError("COPART_CONNECTOR_ENCRYPTION_KEY cannot be blank when set.")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
