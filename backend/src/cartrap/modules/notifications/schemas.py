"""Schemas for push notification subscription APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PushSubscriptionKeys(BaseModel):
    p256dh: str = Field(min_length=1)
    auth: str = Field(min_length=1)


class PushSubscriptionPayload(BaseModel):
    endpoint: str = Field(min_length=1)
    expirationTime: Optional[int] = None
    keys: PushSubscriptionKeys


class PushSubscriptionRequest(BaseModel):
    subscription: PushSubscriptionPayload
    user_agent: Optional[str] = Field(default=None, max_length=255)


class PushSubscriptionResponse(BaseModel):
    id: str
    endpoint: str
    user_agent: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class PushSubscriptionConfigResponse(BaseModel):
    enabled: bool
    public_key: Optional[str] = None
    reason: Optional[str] = None


class PushTestRequest(BaseModel):
    title: str = Field(default="CarTrap test notification", min_length=1, max_length=120)
    body: str = Field(default="Push delivery is working on this device.", min_length=1, max_length=240)


class PushDeliveryResult(BaseModel):
    delivered: int
    failed: int
    removed: int
    endpoints: list[str] = Field(default_factory=list)
