"""Schemas shared by reliability and freshness contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


FreshnessStatus = Literal["live", "cached", "degraded", "outdated", "unknown"]
RefreshStatus = Literal["idle", "repair_pending", "retryable_failure", "failed"]


class FreshnessEnvelopeResponse(BaseModel):
    status: FreshnessStatus
    last_synced_at: Optional[datetime] = None
    stale_after: Optional[datetime] = None
    degraded_reason: Optional[str] = None
    retryable: bool = False


class RefreshStateResponse(BaseModel):
    status: RefreshStatus = "idle"
    last_attempted_at: Optional[datetime] = None
    last_succeeded_at: Optional[datetime] = None
    next_retry_at: Optional[datetime] = None
    error_message: Optional[str] = None
    retryable: bool = False
    priority_class: Optional[str] = None
    last_outcome: Optional[str] = None
    metrics: dict[str, int] = Field(default_factory=dict)
