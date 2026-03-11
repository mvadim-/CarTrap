"""Change detection for lot snapshots."""

from __future__ import annotations

from typing import Any


TRACKED_FIELDS = (
    "status",
    "raw_status",
    "sale_date",
    "current_bid",
    "buy_now_price",
    "currency",
)


def detect_significant_changes(previous_snapshot: dict | None, next_snapshot: dict) -> dict[str, dict[str, Any]]:
    if previous_snapshot is None:
        return {
            field: {"before": None, "after": next_snapshot.get(field)}
            for field in TRACKED_FIELDS
            if next_snapshot.get(field) is not None
        }

    changes: dict[str, dict[str, Any]] = {}
    for field in TRACKED_FIELDS:
        previous_value = previous_snapshot.get(field)
        next_value = next_snapshot.get(field)
        if previous_value != next_value:
            changes[field] = {"before": previous_value, "after": next_value}
    return changes
