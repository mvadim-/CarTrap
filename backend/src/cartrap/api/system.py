"""System endpoints."""

from fastapi import APIRouter, Request


router = APIRouter()


@router.get("/health")
def healthcheck(request: Request) -> dict[str, str]:
    settings = request.app.state.settings
    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.environment,
    }
