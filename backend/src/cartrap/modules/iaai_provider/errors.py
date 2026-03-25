"""IAAI-specific transport, gateway, and auth exceptions."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IaaiDiagnostics:
    """Sanitized failure metadata safe to propagate across the gateway boundary."""

    correlation_id: str | None = None
    step: str | None = None
    error_code: str | None = None
    failure_class: str | None = None
    upstream_status_code: int | None = None
    hint: str | None = None

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {}
        if self.correlation_id:
            payload["correlation_id"] = self.correlation_id
        if self.step:
            payload["step"] = self.step
        if self.error_code:
            payload["error_code"] = self.error_code
        if self.failure_class:
            payload["failure_class"] = self.failure_class
        if self.upstream_status_code is not None:
            payload["upstream_status_code"] = self.upstream_status_code
        if self.hint:
            payload["hint"] = self.hint
        return payload

    @classmethod
    def from_payload(cls, payload: object) -> "IaaiDiagnostics | None":
        if not isinstance(payload, dict):
            return None
        upstream_status = payload.get("upstream_status_code")
        try:
            parsed_status = int(upstream_status) if upstream_status is not None else None
        except (TypeError, ValueError):
            parsed_status = None
        return cls(
            correlation_id=_string_or_none(payload.get("correlation_id")),
            step=_string_or_none(payload.get("step")),
            error_code=_string_or_none(payload.get("error_code")),
            failure_class=_string_or_none(payload.get("failure_class")),
            upstream_status_code=parsed_status,
            hint=_string_or_none(payload.get("hint")),
        )


class IaaiError(Exception):
    """Base IAAI error."""

    def __init__(self, message: str, *, diagnostics: IaaiDiagnostics | None = None) -> None:
        super().__init__(message)
        self.diagnostics = diagnostics


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


class IaaiGatewayUnavailableError(IaaiError):
    """Raised when the NAS-hosted IAAI gateway cannot be reached."""


class IaaiGatewayMalformedResponseError(IaaiError):
    """Raised when the NAS-hosted IAAI gateway returns an invalid payload."""


def _string_or_none(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
