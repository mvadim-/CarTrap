"""Top-level API router."""

from fastapi import APIRouter

from cartrap.modules.admin.router import router as admin_router
from cartrap.modules.auth.router import router as auth_router
from cartrap.modules.search.router import router as search_router
from cartrap.modules.watchlist.router import router as watchlist_router
from cartrap.api.system import router as system_router


api_router = APIRouter()
api_router.include_router(system_router, tags=["system"])
api_router.include_router(auth_router)
api_router.include_router(admin_router)
api_router.include_router(search_router)
api_router.include_router(watchlist_router)
