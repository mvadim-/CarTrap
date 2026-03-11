"""Application configuration."""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    mongo_uri: str = Field(default="mongodb://localhost:27017", alias="MONGO_URI", min_length=1)
    mongo_db: str = Field(default="cartrap", alias="MONGO_DB", min_length=1)
    mongo_ping_on_startup: bool = Field(default=False, alias="MONGO_PING_ON_STARTUP")
    jwt_secret: str = Field(default="change-me", alias="JWT_SECRET", min_length=8)
    jwt_refresh_secret: str = Field(default="change-me-too", alias="JWT_REFRESH_SECRET", min_length=8)
    access_token_ttl_minutes: int = Field(default=30, alias="ACCESS_TOKEN_TTL_MINUTES", ge=1)
    refresh_token_ttl_minutes: int = Field(default=60 * 24 * 14, alias="REFRESH_TOKEN_TTL_MINUTES", ge=1)
    invite_ttl_hours: int = Field(default=72, alias="INVITE_TTL_HOURS", ge=1)
    bootstrap_admin_email: Optional[str] = Field(default=None, alias="BOOTSTRAP_ADMIN_EMAIL")
    bootstrap_admin_password: Optional[str] = Field(default=None, alias="BOOTSTRAP_ADMIN_PASSWORD")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
