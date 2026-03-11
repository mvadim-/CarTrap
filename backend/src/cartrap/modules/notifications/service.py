"""Push subscription and delivery services."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol

from fastapi import HTTPException, status
from pymongo.database import Database

from cartrap.modules.notifications.repository import NotificationRepository


class PushSender(Protocol):
    def send(self, subscription: dict, payload: dict) -> None:
        ...


class WebPushSender:
    """Placeholder sender for the MVP backend layer."""

    def send(self, subscription: dict, payload: dict) -> None:
        del subscription
        del payload
        return None


class NotificationService:
    def __init__(self, database: Database, sender: PushSender | None = None) -> None:
        self.repository = NotificationRepository(database)
        self.repository.ensure_indexes()
        self._sender = sender or WebPushSender()

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

    def send_lot_change_notification(self, event: dict) -> dict:
        subscriptions = self.repository.get_subscriptions_for_owner(event["owner_user_id"])
        delivered = 0
        failed = 0
        removed = 0
        delivered_endpoints: list[str] = []

        payload = {
            "title": f"Lot {event['lot_number']} updated",
            "body": ", ".join(sorted(event["changes"].keys())),
            "tracked_lot_id": event["tracked_lot_id"],
            "changes": event["changes"],
        }

        for subscription in subscriptions:
            try:
                self._sender.send(subscription, payload)
                delivered += 1
                delivered_endpoints.append(subscription["endpoint"])
            except Exception:
                failed += 1
                self.repository.delete_subscription_by_id(str(subscription["_id"]))
                removed += 1

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
