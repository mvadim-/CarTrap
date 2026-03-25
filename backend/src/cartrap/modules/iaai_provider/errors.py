"""IAAI-specific transport and auth exceptions."""

from __future__ import annotations


class IaaiError(Exception):
    """Base IAAI error."""


class IaaiAuthenticationError(IaaiError):
    """IAAI credentials were rejected."""


class IaaiRefreshError(IaaiError):
    """Stored refresh token can no longer renew the access token."""


class IaaiSessionInvalidError(IaaiError):
    """Stored IAAI session bundle is no longer valid."""


class IaaiWafError(IaaiError):
    """IAAI/Imperva rejected the request."""


class IaaiConfigurationError(IaaiError):
    """IAAI client configuration is invalid."""

