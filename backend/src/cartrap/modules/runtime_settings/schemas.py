"""Pydantic schemas for runtime settings service and admin API."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from cartrap.modules.runtime_settings.models import RuntimeSettingValue, RuntimeSettingValueType


class RuntimeSettingResponse(BaseModel):
    key: str
    category: str
    label: str
    description: str
    value_type: RuntimeSettingValueType
    restart_required: bool = False
    default_value: RuntimeSettingValue
    override_value: Optional[RuntimeSettingValue] = None
    effective_value: RuntimeSettingValue
    updated_by: Optional[str] = None
    updated_at: Optional[datetime] = None
    min_value: Optional[int] = None
    max_value: Optional[int] = None
    min_items: Optional[int] = None
    max_items: Optional[int] = None
    step: int = 1
    unit: Optional[str] = None
    is_overridden: bool = False


class RuntimeSettingsGroupResponse(BaseModel):
    key: str
    label: str
    items: List[RuntimeSettingResponse] = Field(default_factory=list)


class RuntimeSettingUpdatePayload(BaseModel):
    key: str
    value: RuntimeSettingValue


class RuntimeSettingsUpdatePayload(BaseModel):
    updates: List[RuntimeSettingUpdatePayload] = Field(default_factory=list, min_length=1)


class RuntimeSettingsResetPayload(BaseModel):
    keys: List[str] = Field(default_factory=list, min_length=1)
