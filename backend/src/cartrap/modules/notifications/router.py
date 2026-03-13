"""Push subscription API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, status

from cartrap.api.dependencies import get_current_user
from cartrap.modules.notifications.schemas import (
    PushSubscriptionConfigResponse,
    PushDeliveryResult,
    PushSubscriptionRequest,
    PushSubscriptionResponse,
    PushTestRequest,
)
from cartrap.modules.notifications.service import NotificationService


router = APIRouter(prefix="/notifications", tags=["notifications"])


def get_notification_service(request: Request) -> NotificationService:
    sender = getattr(request.app.state, "web_push_sender", None)
    settings = request.app.state.settings
    return NotificationService(
        request.app.state.mongo.database,
        sender=sender,
        vapid_public_key=settings.vapid_public_key,
        vapid_private_key=settings.vapid_private_key,
        vapid_subject=settings.vapid_subject,
    )


@router.get("/subscriptions")
def list_subscriptions(
    current_user: dict = Depends(get_current_user),
    notification_service: NotificationService = Depends(get_notification_service),
) -> dict:
    return notification_service.list_subscriptions(current_user)


@router.get("/subscription-config", response_model=PushSubscriptionConfigResponse)
def get_subscription_config(
    current_user: dict = Depends(get_current_user),
    notification_service: NotificationService = Depends(get_notification_service),
) -> dict:
    del current_user
    return notification_service.get_subscription_config()


@router.post("/subscriptions", response_model=PushSubscriptionResponse, status_code=status.HTTP_201_CREATED)
def subscribe(
    payload: PushSubscriptionRequest,
    current_user: dict = Depends(get_current_user),
    notification_service: NotificationService = Depends(get_notification_service),
) -> dict:
    return notification_service.upsert_subscription(current_user, payload.model_dump(mode="python"))


@router.post("/test", response_model=PushDeliveryResult)
def send_test_push(
    payload: PushTestRequest,
    current_user: dict = Depends(get_current_user),
    notification_service: NotificationService = Depends(get_notification_service),
) -> dict:
    return notification_service.send_test_notification(current_user, payload.title, payload.body)


@router.delete("/subscriptions", status_code=status.HTTP_204_NO_CONTENT)
def unsubscribe(
    endpoint: str = Query(..., min_length=1),
    current_user: dict = Depends(get_current_user),
    notification_service: NotificationService = Depends(get_notification_service),
) -> None:
    notification_service.unsubscribe(current_user, endpoint)
