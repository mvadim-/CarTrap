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
from cartrap.modules.notifications.service import build_web_push_sender
from cartrap.modules.runtime_settings.service import RuntimeSettingsService
from cartrap.modules.search.service import SearchService


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = app.state.settings
    configure_logging(settings.log_level)

    mongo = MongoManager(settings.mongo_uri, settings.mongo_db, settings.mongo_ping_on_startup)
    mongo.connect()
    runtime_settings_service = RuntimeSettingsService(mongo.database, settings)

    app.state.settings = settings
    app.state.mongo = mongo
    app.state.runtime_settings_service = runtime_settings_service
    set_service_factory(app, lambda: AuthService(mongo.database, settings, runtime_settings_service=runtime_settings_service))
    AuthService(mongo.database, settings, runtime_settings_service=runtime_settings_service).ensure_bootstrap_admin()
    SearchService(
        mongo.database,
        saved_search_poll_interval_minutes=runtime_settings_service.get_effective_value("saved_search_poll_interval_minutes"),
    ).ensure_catalog_seeded()
    app.state.web_push_sender = build_web_push_sender(settings.vapid_private_key, settings.vapid_subject)

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
        allow_origin_regex=app_settings.cors_origin_regex,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router, prefix=app_settings.api_prefix)
    return app


app = create_app()
