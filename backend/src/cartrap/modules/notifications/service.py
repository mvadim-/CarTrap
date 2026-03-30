"""Push subscription and delivery services."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from typing import Protocol

from fastapi import HTTPException, status
from pymongo.database import Database
from pywebpush import WebPushException, webpush

from cartrap.modules.notifications.repository import NotificationRepository


LOGGER = logging.getLogger(__name__)

CHANGE_LABELS = {
    "raw_status": "Status",
    "status": "Status",
    "sale_date": "Sale",
    "current_bid": "Bid",
    "buy_now_price": "Buy now",
    "currency": "Currency",
}


class PushSender(Protocol):
    def send(self, subscription: dict, payload: dict) -> None:
        ...


class PushDeliveryError(Exception):
    def __init__(self, message: str, *, unrecoverable: bool) -> None:
        super().__init__(message)
        self.unrecoverable = unrecoverable


class WebPushSender:
    def __init__(self, vapid_private_key: str, vapid_subject: str) -> None:
        self._vapid_private_key = vapid_private_key
        self._vapid_subject = vapid_subject

    def send(self, subscription: dict, payload: dict) -> None:
        try:
            webpush(
                subscription_info={
                    "endpoint": subscription["endpoint"],
                    "keys": subscription["keys"],
                },
                data=json.dumps(payload),
                vapid_private_key=self._vapid_private_key,
                vapid_claims={"sub": self._vapid_subject},
            )
        except WebPushException as exc:
            response = getattr(exc, "response", None)
            status_code = getattr(response, "status_code", None)
            raise PushDeliveryError(
                str(exc),
                unrecoverable=status_code in {404, 410},
            ) from exc
        except Exception as exc:
            raise PushDeliveryError(str(exc), unrecoverable=False) from exc


def build_web_push_sender(
    vapid_private_key: str | None,
    vapid_subject: str | None,
) -> PushSender | None:
    missing = _missing_vapid_fields(
        vapid_public_key="present-for-delivery-check",
        vapid_private_key=vapid_private_key,
        vapid_subject=vapid_subject,
    )
    if missing:
        return None
    return WebPushSender(vapid_private_key=vapid_private_key.strip(), vapid_subject=vapid_subject.strip())


def _is_missing_config_value(value: str | None) -> bool:
    return value is None or not value.strip() or value.strip().lower() == "replace-me"


def _missing_vapid_fields(
    vapid_public_key: str | None,
    vapid_private_key: str | None,
    vapid_subject: str | None,
) -> list[str]:
    missing: list[str] = []
    if _is_missing_config_value(vapid_public_key):
        missing.append("VAPID_PUBLIC_KEY")
    if _is_missing_config_value(vapid_private_key):
        missing.append("VAPID_PRIVATE_KEY")
    if _is_missing_config_value(vapid_subject):
        missing.append("VAPID_SUBJECT")
    return missing


def build_subscription_config(
    vapid_public_key: str | None,
    vapid_private_key: str | None,
    vapid_subject: str | None,
) -> dict:
    missing = _missing_vapid_fields(vapid_public_key, vapid_private_key, vapid_subject)
    if missing:
        return {
            "enabled": False,
            "public_key": None,
            "reason": f"Push notifications are not configured on the server. Missing: {', '.join(missing)}.",
        }
    return {"enabled": True, "public_key": vapid_public_key.strip(), "reason": None}


class NotificationService:
    def __init__(
        self,
        database: Database,
        sender: PushSender | None = None,
        vapid_public_key: str | None = None,
        vapid_private_key: str | None = None,
        vapid_subject: str | None = None,
    ) -> None:
        self.repository = NotificationRepository(database)
        self.repository.ensure_indexes()
        self._sender = sender
        self._vapid_public_key = vapid_public_key
        self._vapid_private_key = vapid_private_key
        self._vapid_subject = vapid_subject

    def upsert_subscription(self, owner_user: dict, payload: dict) -> dict:
        now = self._now()
        document = self.repository.upsert_subscription(
            owner_user["id"],
            {
                "endpoint": payload["subscription"]["endpoint"],
                "expiration_time": payload["subscription"].get("expirationTime"),
                "keys": payload["subscription"]["keys"],
                "user_agent": payload.get("user_agent"),
                "updated_at": now,
            },
        )
        return self.serialize_subscription(document)

    def list_subscriptions(self, owner_user: dict) -> dict:
        return {"items": [self.serialize_subscription(item) for item in self.repository.list_subscriptions_for_owner(owner_user["id"])]}

    def unsubscribe(self, owner_user: dict, endpoint: str) -> None:
        deleted = self.repository.delete_subscription(owner_user["id"], endpoint)
        if deleted == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found.")

    def get_subscription_config(self) -> dict:
        return build_subscription_config(
            vapid_public_key=self._vapid_public_key,
            vapid_private_key=self._vapid_private_key,
            vapid_subject=self._vapid_subject,
        )

    def send_test_notification(self, owner_user: dict, title: str, body: str) -> dict:
        payload = {
            "title": title,
            "body": body,
            "test": True,
            "notification_type": "test",
            "refresh_targets": [],
        }
        return self._send_payload_to_owner(owner_user["id"], payload)

    def send_saved_search_match_notification(self, event: dict) -> dict:
        payload = {
            "title": "CarTrap",
            "body": f"З'явилось {event['new_matches']} нових лотів для пошуку машини {event['search_title']}",
            "saved_search_id": event["saved_search_id"],
            "result_count": event["result_count"],
            "new_matches": event["new_matches"],
            "notification_type": "saved_search_match",
            "refresh_targets": ["savedSearches", "liveSync"],
        }
        dedupe_suffix = ",".join(self._dedupe_saved_search_matches(event))
        dedupe_key = f"saved_search_match:{event['saved_search_id']}:{event.get('result_count')}:{dedupe_suffix}"
        return self._send_payload_to_owner(event["owner_user_id"], payload, dedupe_key=dedupe_key)

    def send_lot_change_notification(self, event: dict) -> dict:
        change_summary = self._format_change_summary(event["changes"], currency=event.get("currency"))
        payload = {
            "title": f"{event['title']} ({event['lot_number']})",
            "body": change_summary,
            "tracked_lot_id": event["tracked_lot_id"],
            "changes": event["changes"],
            "notification_type": "lot_change",
            "refresh_targets": ["watchlist", "liveSync"],
        }
        dedupe_key = f"lot_change:{event['tracked_lot_id']}:{event.get('snapshot_id')}"
        return self._send_payload_to_owner(event["owner_user_id"], payload, dedupe_key=dedupe_key)

    def send_auction_reminder_notification(self, event: dict) -> dict:
        payload = {
            "title": f"{event['title']} ({event['lot_number']})",
            "body": self._format_auction_reminder_body(event["reminder_offset_minutes"]),
            "tracked_lot_id": event["tracked_lot_id"],
            "sale_date": event.get("sale_date"),
            "reminder_offset_minutes": event["reminder_offset_minutes"],
            "notification_type": "auction_reminder",
            "refresh_targets": ["watchlist", "liveSync"],
        }
        dedupe_key = (
            f"auction_reminder:{event['tracked_lot_id']}:{event.get('sale_date')}:{event['reminder_offset_minutes']}"
        )
        return self._send_payload_to_owner(event["owner_user_id"], payload, dedupe_key=dedupe_key)

    def _send_payload_to_owner(self, owner_user_id: str, payload: dict, *, dedupe_key: str | None = None) -> dict:
        if self._sender is None:
            LOGGER.warning(
                "Push delivery skipped because sender is not configured.",
                extra={"owner_user_id": owner_user_id, "payload_keys": sorted(payload.keys())},
            )
            return {
                "delivered": 0,
                "failed": 0,
                "removed": 0,
                "endpoints": [],
            }
        subscriptions = self.repository.get_subscriptions_for_owner(owner_user_id)
        delivered = 0
        failed = 0
        removed = 0
        delivered_endpoints: list[str] = []

        for subscription in subscriptions:
            endpoint_dedupe_key = None
            if dedupe_key:
                endpoint_dedupe_key = f"{dedupe_key}:{subscription['endpoint']}"
                if self.repository.has_delivery_receipt(endpoint_dedupe_key):
                    LOGGER.info(
                        "Skipped duplicate push delivery.",
                        extra={
                            "owner_user_id": owner_user_id,
                            "endpoint": subscription["endpoint"],
                            "dedupe_key": endpoint_dedupe_key,
                        },
                    )
                    continue
            try:
                self._sender.send(subscription, payload)
                if endpoint_dedupe_key:
                    self.repository.create_delivery_receipt(
                        endpoint_dedupe_key,
                        {
                            "owner_user_id": owner_user_id,
                            "endpoint": subscription["endpoint"],
                            "notification_type": payload.get("notification_type"),
                            "created_at": self._now(),
                        },
                    )
                delivered += 1
                delivered_endpoints.append(subscription["endpoint"])
                LOGGER.info(
                    "Push notification delivered.",
                    extra={
                        "owner_user_id": owner_user_id,
                        "endpoint": subscription["endpoint"],
                        "payload_keys": sorted(payload.keys()),
                    },
                )
            except PushDeliveryError as exc:
                failed += 1
                LOGGER.warning(
                    "Push delivery failed.",
                    extra={
                        "owner_user_id": owner_user_id,
                        "endpoint": subscription["endpoint"],
                        "unrecoverable": exc.unrecoverable,
                        "reason": str(exc),
                    },
                )
                if exc.unrecoverable:
                    self.repository.delete_subscription_by_id(str(subscription["_id"]))
                    removed += 1
                    LOGGER.info(
                        "Removed invalid push subscription after unrecoverable delivery failure.",
                        extra={"owner_user_id": owner_user_id, "endpoint": subscription["endpoint"]},
                    )
            except Exception:
                failed += 1
                LOGGER.exception(
                    "Unexpected push delivery failure.",
                    extra={
                        "owner_user_id": owner_user_id,
                        "endpoint": subscription.get("endpoint"),
                    },
                )

        return {
            "delivered": delivered,
            "failed": failed,
            "removed": removed,
            "endpoints": delivered_endpoints,
        }

    @staticmethod
    def serialize_subscription(document: dict) -> dict:
        return {
            "id": str(document["_id"]),
            "endpoint": document["endpoint"],
            "user_agent": document.get("user_agent"),
            "created_at": document["created_at"],
            "updated_at": document["updated_at"],
        }

    @classmethod
    def _format_change_summary(cls, changes: dict, currency: str | None = None) -> str:
        formatted_parts = []
        for field_name, change in cls._iter_display_changes(changes):
            label = CHANGE_LABELS.get(field_name, field_name.replace("_", " ").title())
            before_value = cls._format_change_value(field_name, change.get("before"))
            after_value = cls._format_change_value(field_name, change.get("after"))
            if before_value == after_value:
                continue
            if field_name in {"current_bid", "buy_now_price"} and currency:
                formatted_parts.append(f"{label}: {before_value} -> {after_value} {currency}")
            else:
                formatted_parts.append(f"{label}: {before_value} -> {after_value}")
        if not formatted_parts:
            return "Tracked lot details changed."
        return "; ".join(formatted_parts)

    @staticmethod
    def _iter_display_changes(changes: dict):
        has_raw_status = "raw_status" in changes
        for field_name in ("raw_status", "status", "current_bid", "buy_now_price", "sale_date", "currency"):
            if field_name not in changes:
                continue
            if field_name == "status" and has_raw_status:
                continue
            yield field_name, changes[field_name]
        for field_name, change in changes.items():
            if field_name in {"raw_status", "status", "current_bid", "buy_now_price", "sale_date", "currency"}:
                continue
            yield field_name, change

    @staticmethod
    def _format_change_value(field_name: str, value: object) -> str:
        if value is None:
            return "none"
        if field_name in {"current_bid", "buy_now_price"} and isinstance(value, (int, float)):
            digits = 0 if float(value).is_integer() else 2
            return f"{value:,.{digits}f}"
        if field_name == "sale_date":
            if isinstance(value, datetime):
                return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            return str(value)
        return str(value)

    @staticmethod
    def _format_auction_reminder_body(reminder_offset_minutes: int) -> str:
        if reminder_offset_minutes == 0:
            return "Auction started."
        if reminder_offset_minutes == 60:
            return "Auction starts in 1 hour."
        return f"Auction starts in {reminder_offset_minutes} min."

    @staticmethod
    def _dedupe_saved_search_matches(event: dict) -> list[str]:
        identifiers = event.get("new_lot_keys") or event.get("new_lot_numbers") or []
        if not isinstance(identifiers, list):
            return []
        return [str(item) for item in identifiers if item]

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)
