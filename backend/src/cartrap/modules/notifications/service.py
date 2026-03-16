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
        }
        return self._send_payload_to_owner(owner_user["id"], payload)

    def send_saved_search_match_notification(self, event: dict) -> dict:
        payload = {
            "title": "CarTrap",
            "body": f"З'явилось {event['new_matches']} нових лотів для пошуку машини {event['search_title']}",
            "saved_search_id": event["saved_search_id"],
            "result_count": event["result_count"],
            "new_matches": event["new_matches"],
        }
        return self._send_payload_to_owner(event["owner_user_id"], payload)

    def send_lot_change_notification(self, event: dict) -> dict:
        payload = {
            "title": f"Lot {event['lot_number']} updated",
            "body": ", ".join(sorted(event["changes"].keys())),
            "tracked_lot_id": event["tracked_lot_id"],
            "changes": event["changes"],
        }
        return self._send_payload_to_owner(event["owner_user_id"], payload)

    def _send_payload_to_owner(self, owner_user_id: str, payload: dict) -> dict:
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
            try:
                self._sender.send(subscription, payload)
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

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)
