"""Explicit error types for Copart transport and gateway failures."""

from __future__ import annotations

from typing import Optional


class CopartClientError(RuntimeError):
    """Base exception for Copart transport failures."""


class CopartConfigurationError(CopartClientError):
    """Raised when required transport configuration is missing or invalid."""


class CopartAuthenticationError(CopartClientError):
    """Raised when Copart rejects connector credentials."""


class CopartLoginRejectedError(CopartClientError):
    """Raised when Copart rejects the connector login request profile before auth succeeds."""

    def __init__(self, message: str, *, status_code: Optional[int] = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class CopartChallengeError(CopartClientError):
    """Raised when the native challenge/bootstrap flow cannot be replayed."""


class CopartSessionInvalidError(CopartClientError):
    """Raised when an existing session bundle is no longer authorized."""


class CopartRateLimitError(CopartClientError):
    """Raised when the gateway applies connector connect throttling."""


class CopartGatewayError(CopartClientError):
    """Base exception for NAS gateway failures."""


class CopartGatewayUnavailableError(CopartGatewayError):
    """Raised when the NAS gateway cannot be reached or is temporarily unavailable."""


class CopartGatewayUpstreamError(CopartGatewayError):
    """Raised when the NAS gateway reports a Copart-side rejection or upstream failure."""

    def __init__(self, message: str, *, upstream_status_code: Optional[int] = None) -> None:
        super().__init__(message)
        self.upstream_status_code = upstream_status_code


class CopartGatewayMalformedResponseError(CopartGatewayError):
    """Raised when the NAS gateway returns an invalid or unexpected response."""
