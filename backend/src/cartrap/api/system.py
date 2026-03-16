"""System endpoints."""

from fastapi import APIRouter, Request

from cartrap.modules.system_status.service import SystemStatusService


router = APIRouter()


@router.get("/health")
def healthcheck(request: Request) -> dict[str, str]:
    settings = request.app.state.settings
    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.environment,
    }


@router.get("/system/status")
def system_status(request: Request) -> dict:
    settings = request.app.state.settings
    status_service = SystemStatusService(request.app.state.mongo.database)
    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.environment,
        "live_sync": status_service.get_live_sync_status(),
    }
