"""System endpoints."""

from datetime import timedelta

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
    runtime_values = request.app.state.runtime_settings_service.get_effective_values(
        [
            "saved_search_poll_interval_minutes",
            "watchlist_default_poll_interval_minutes",
            "live_sync_stale_after_minutes",
        ]
    )
    status_service = SystemStatusService(
        request.app.state.mongo.database,
        live_sync_stale_after_minutes=int(runtime_values["live_sync_stale_after_minutes"]),
    )
    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.environment,
        "live_sync": status_service.get_live_sync_status(),
        "freshness_policies": {
            "saved_searches": {
                "stale_after_seconds": int(timedelta(minutes=int(runtime_values["saved_search_poll_interval_minutes"])).total_seconds()),
            },
            "watchlist": {
                "stale_after_seconds": int(
                    timedelta(minutes=int(runtime_values["watchlist_default_poll_interval_minutes"])).total_seconds()
                ),
            },
        },
    }
