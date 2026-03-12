"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from cartrap.api.router import api_router
from cartrap.api.dependencies import set_service_factory
from cartrap.config import Settings, get_settings
from cartrap.core.logging import configure_logging
from cartrap.db.mongo import MongoManager
from cartrap.modules.auth.service import AuthService
from cartrap.modules.notifications.service import WebPushSender
from cartrap.modules.search.service import SearchService


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = app.state.settings
    configure_logging(settings.log_level)

    mongo = MongoManager(settings.mongo_uri, settings.mongo_db, settings.mongo_ping_on_startup)
    mongo.connect()

    app.state.settings = settings
    app.state.mongo = mongo
    set_service_factory(app, lambda: AuthService(mongo.database, settings))
    AuthService(mongo.database, settings).ensure_bootstrap_admin()
    SearchService(mongo.database).ensure_catalog_seeded()
    app.state.web_push_sender = WebPushSender()

    try:
        yield
    finally:
        mongo.close()


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    if settings is not None:
        app_settings = settings
    else:
        app_settings = get_settings()

    app = FastAPI(title=app_settings.app_name, lifespan=lifespan)
    app.state.settings = app_settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router, prefix=app_settings.api_prefix)
    return app


app = create_app()
