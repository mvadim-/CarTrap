"""Push subscription API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, status

from cartrap.api.dependencies import get_current_user
from cartrap.modules.notifications.schemas import PushSubscriptionRequest, PushSubscriptionResponse
from cartrap.modules.notifications.service import NotificationService


router = APIRouter(prefix="/notifications", tags=["notifications"])


def get_notification_service(request: Request) -> NotificationService:
    sender = getattr(request.app.state, "web_push_sender", None)
    return NotificationService(request.app.state.mongo.database, sender=sender)


@router.get("/subscriptions")
def list_subscriptions(
    current_user: dict = Depends(get_current_user),
    notification_service: NotificationService = Depends(get_notification_service),
) -> dict:
    return notification_service.list_subscriptions(current_user)


@router.post("/subscriptions", response_model=PushSubscriptionResponse, status_code=status.HTTP_201_CREATED)
def subscribe(
    payload: PushSubscriptionRequest,
    current_user: dict = Depends(get_current_user),
    notification_service: NotificationService = Depends(get_notification_service),
) -> dict:
    return notification_service.upsert_subscription(current_user, payload.model_dump(mode="python"))


@router.delete("/subscriptions", status_code=status.HTTP_204_NO_CONTENT)
def unsubscribe(
    endpoint: str = Query(..., min_length=1),
    current_user: dict = Depends(get_current_user),
    notification_service: NotificationService = Depends(get_notification_service),
) -> None:
    notification_service.unsubscribe(current_user, endpoint)
