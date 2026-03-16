"""FastAPI application factory for NAS-hosted Copart gateway."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI

from cartrap.config import Settings, get_settings
from cartrap.core.logging import configure_logging
from cartrap.modules.copart_gateway.router import router as gateway_router
from cartrap.modules.copart_gateway.service import CopartGatewayService


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = app.state.settings
    configure_logging(settings.log_level)
    app.state.settings = settings
    app.state.gateway_service_factory = lambda: CopartGatewayService(settings=settings)
    yield


def create_gateway_app(settings: Optional[Settings] = None) -> FastAPI:
    app_settings = settings or get_settings()
    app = FastAPI(title=f"{app_settings.app_name} Gateway", lifespan=lifespan)
    app.state.settings = app_settings
    app.include_router(gateway_router)
    return app


app = create_gateway_app()
