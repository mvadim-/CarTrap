"""Runtime settings resolver backed by Mongo overrides and env defaults."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from fastapi import HTTPException, status
from pymongo.database import Database

from cartrap.config import Settings
from cartrap.modules.runtime_settings.models import (
    RUNTIME_SETTINGS_GROUP_LABELS,
    RuntimeSettingDefinition,
    RuntimeSettingValue,
    get_runtime_setting_definition,
    list_runtime_setting_definitions,
)
from cartrap.modules.runtime_settings.repository import RuntimeSettingsRepository
from cartrap.modules.runtime_settings.schemas import RuntimeSettingResponse, RuntimeSettingsGroupResponse


if hasattr(status, "HTTP_422_UNPROCESSABLE_CONTENT"):
    HTTP_422_STATUS = status.HTTP_422_UNPROCESSABLE_CONTENT
else:
    HTTP_422_STATUS = status.HTTP_422_UNPROCESSABLE_ENTITY


class RuntimeSettingsService:
    def __init__(
        self,
        database: Database,
        settings: Settings,
        *,
        now_provider=None,
    ) -> None:
        self._settings = settings
        self._repository = RuntimeSettingsRepository(database)
        self._repository.ensure_indexes()
        self._now_provider = now_provider or self._now

    def list_settings(self) -> list[dict]:
        overrides_by_key = {document["key"]: document for document in self._repository.list_overrides()}
        items: list[dict] = []
        for definition in list_runtime_setting_definitions():
            items.append(self._build_setting_response(definition, overrides_by_key.get(definition.key)).model_dump(mode="json"))
        return items

    def list_settings_grouped(self) -> list[dict]:
        grouped: dict[str, list[dict]] = {}
        for item in self.list_settings():
            grouped.setdefault(item["category"], []).append(item)
        return [
            RuntimeSettingsGroupResponse(
                key=group_key,
                label=RUNTIME_SETTINGS_GROUP_LABELS.get(group_key, group_key.replace("_", " ").title()),
                items=grouped[group_key],
            ).model_dump(mode="json")
            for group_key in grouped
        ]

    def get_effective_value(self, key: str) -> RuntimeSettingValue:
        definition = self._require_definition(key)
        override = self._repository.find_override(key)
        return self._resolve_effective_value(definition, override)

    def get_effective_values(self, keys: Iterable[str] | None = None) -> dict[str, RuntimeSettingValue]:
        selected_keys = list(keys) if keys is not None else [definition.key for definition in list_runtime_setting_definitions()]
        overrides_by_key = {document["key"]: document for document in self._repository.list_overrides()}
        resolved: dict[str, RuntimeSettingValue] = {}
        for key in selected_keys:
            definition = self._require_definition(key)
            resolved[key] = self._resolve_effective_value(definition, overrides_by_key.get(key))
        return resolved

    def update_settings(self, updates: dict[str, RuntimeSettingValue], *, updated_by: str) -> list[dict]:
        normalized_updates: dict[str, tuple[RuntimeSettingDefinition, RuntimeSettingValue]] = {}
        for key, raw_value in updates.items():
            definition = self._require_definition(key)
            normalized_updates[key] = (definition, self.validate_value(definition, raw_value))

        updated_at = self._now_provider()
        for key, (definition, value) in normalized_updates.items():
            self._repository.upsert_override(
                key=key,
                value=value,
                value_type=definition.value_type,
                updated_by=updated_by,
                updated_at=updated_at,
            )
        return self.list_settings()

    def reset_settings(self, keys: list[str]) -> list[dict]:
        normalized_keys = [self._require_definition(key).key for key in keys]
        self._repository.delete_overrides(normalized_keys)
        return self.list_settings()

    def validate_value(self, definition: RuntimeSettingDefinition, raw_value: RuntimeSettingValue) -> RuntimeSettingValue:
        if definition.value_type == "integer":
            return self._validate_integer(definition, raw_value)
        if definition.value_type == "integer_list":
            return self._validate_integer_list(definition, raw_value)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unsupported runtime setting type for '{definition.key}'.")

    def _build_setting_response(self, definition: RuntimeSettingDefinition, override: dict | None) -> RuntimeSettingResponse:
        default_value = self._get_default_value(definition)
        override_value = self._coerce_override_value(definition, override)
        effective_value = override_value if override_value is not None else default_value
        updated_at = override.get("updated_at") if override else None
        return RuntimeSettingResponse(
            key=definition.key,
            category=definition.category,
            label=definition.label,
            description=definition.description,
            value_type=definition.value_type,
            restart_required=definition.restart_required,
            default_value=default_value,
            override_value=override_value,
            effective_value=effective_value,
            updated_by=override.get("updated_by") if override else None,
            updated_at=updated_at,
            min_value=definition.min_value,
            max_value=definition.max_value,
            min_items=definition.min_items,
            max_items=definition.max_items,
            step=definition.step,
            unit=definition.unit,
            is_overridden=override_value is not None,
        )

    def _resolve_effective_value(self, definition: RuntimeSettingDefinition, override: dict | None) -> RuntimeSettingValue:
        override_value = self._coerce_override_value(definition, override)
        if override_value is not None:
            return override_value
        return self._get_default_value(definition)

    def _coerce_override_value(
        self,
        definition: RuntimeSettingDefinition,
        override: dict | None,
    ) -> RuntimeSettingValue | None:
        if override is None or "value" not in override:
            return None
        try:
            return self.validate_value(definition, override["value"])
        except HTTPException:
            return None

    def _get_default_value(self, definition: RuntimeSettingDefinition) -> RuntimeSettingValue:
        value = getattr(self._settings, definition.settings_field)
        if definition.value_type == "integer_list":
            return [int(item) for item in value]
        return int(value)

    @staticmethod
    def _require_definition(key: str) -> RuntimeSettingDefinition:
        try:
            return get_runtime_setting_definition(key)
        except KeyError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Runtime setting '{key}' is not allowlisted.",
            ) from exc

    def _validate_integer(self, definition: RuntimeSettingDefinition, raw_value: RuntimeSettingValue) -> int:
        if isinstance(raw_value, bool) or isinstance(raw_value, list):
                raise HTTPException(
                    status_code=HTTP_422_STATUS,
                    detail=f"Runtime setting '{definition.key}' expects an integer value.",
                )
        try:
            value = int(raw_value)
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=HTTP_422_STATUS,
                detail=f"Runtime setting '{definition.key}' expects an integer value.",
            ) from exc
        if definition.min_value is not None and value < definition.min_value:
            raise HTTPException(
                status_code=HTTP_422_STATUS,
                detail=f"Runtime setting '{definition.key}' must be at least {definition.min_value}.",
            )
        if definition.max_value is not None and value > definition.max_value:
            raise HTTPException(
                status_code=HTTP_422_STATUS,
                detail=f"Runtime setting '{definition.key}' cannot exceed {definition.max_value}.",
            )
        return value

    def _validate_integer_list(self, definition: RuntimeSettingDefinition, raw_value: RuntimeSettingValue) -> list[int]:
        if not isinstance(raw_value, list):
            raise HTTPException(
                status_code=HTTP_422_STATUS,
                detail=f"Runtime setting '{definition.key}' expects a list of integers.",
            )
        values: list[int] = []
        for item in raw_value:
            if isinstance(item, bool):
                raise HTTPException(
                    status_code=HTTP_422_STATUS,
                    detail=f"Runtime setting '{definition.key}' expects a list of integers.",
                )
            try:
                parsed = int(item)
            except (TypeError, ValueError) as exc:
                raise HTTPException(
                    status_code=HTTP_422_STATUS,
                    detail=f"Runtime setting '{definition.key}' expects a list of integers.",
                ) from exc
            if definition.min_value is not None and parsed < definition.min_value:
                raise HTTPException(
                    status_code=HTTP_422_STATUS,
                    detail=f"Runtime setting '{definition.key}' cannot contain values below {definition.min_value}.",
                )
            if definition.max_value is not None and parsed > definition.max_value:
                raise HTTPException(
                    status_code=HTTP_422_STATUS,
                    detail=f"Runtime setting '{definition.key}' cannot contain values above {definition.max_value}.",
                )
            values.append(parsed)
        normalized = sorted(set(values), reverse=True)
        if definition.min_items is not None and len(normalized) < definition.min_items:
            raise HTTPException(
                status_code=HTTP_422_STATUS,
                detail=f"Runtime setting '{definition.key}' requires at least {definition.min_items} value(s).",
            )
        if definition.max_items is not None and len(normalized) > definition.max_items:
            raise HTTPException(
                status_code=HTTP_422_STATUS,
                detail=f"Runtime setting '{definition.key}' allows at most {definition.max_items} value(s).",
            )
        return normalized

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)
