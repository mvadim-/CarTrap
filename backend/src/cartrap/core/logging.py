"""Logging helpers."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any
from uuid import uuid4


def _normalize_log_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, BaseException):
        return str(value)
    if isinstance(value, dict):
        return {key: _normalize_log_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize_log_value(item) for item in value]
    return value


class StructuredFormatter(logging.Formatter):
    """Emit JSON lines so log processors can index operational fields."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.utcfromtimestamp(record.created).isoformat(timespec="milliseconds") + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        event = getattr(record, "event", None)
        if event:
            payload["event"] = event
        structured = getattr(record, "structured", None)
        if isinstance(structured, dict):
            payload.update({key: _normalize_log_value(value) for key, value in structured.items() if value is not None})
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=True, sort_keys=True)


def make_log_extra(event: str, **fields: Any) -> dict[str, Any]:
    return {
        "event": event,
        "structured": {key: _normalize_log_value(value) for key, value in fields.items() if value is not None},
    }


def new_correlation_id(prefix: str | None = None) -> str:
    token = uuid4().hex
    return f"{prefix}-{token}" if prefix else token


def configure_logging(log_level: str) -> None:
    """Configure root logging once for the process."""
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    if not root_logger.handlers:
        root_logger.addHandler(logging.StreamHandler())
    for handler in root_logger.handlers:
        handler.setFormatter(StructuredFormatter())
