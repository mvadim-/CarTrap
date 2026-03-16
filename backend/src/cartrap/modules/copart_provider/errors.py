"""Explicit error types for Copart transport and gateway failures."""

from __future__ import annotations

from typing import Optional


class CopartClientError(RuntimeError):
    """Base exception for Copart transport failures."""


class CopartConfigurationError(CopartClientError):
    """Raised when required transport configuration is missing or invalid."""


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
