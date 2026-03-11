"""Search service built on top of the Copart provider."""

from __future__ import annotations

from typing import Callable, Optional

from fastapi import HTTPException, status
from pymongo.database import Database

from cartrap.modules.copart_provider.models import CopartSearchResult
from cartrap.modules.copart_provider.service import CopartProvider
from cartrap.modules.search.schemas import SearchRequest
from cartrap.modules.watchlist.service import WatchlistService


class SearchService:
    def __init__(
        self,
        database: Database,
        provider_factory: Optional[Callable[[], CopartProvider]] = None,
        watchlist_service_factory: Optional[Callable[[], WatchlistService]] = None,
    ) -> None:
        self._provider_factory = provider_factory or CopartProvider
        self._watchlist_service_factory = watchlist_service_factory or (lambda: WatchlistService(database, provider_factory=provider_factory))

    def search(self, payload: SearchRequest) -> dict:
        source_url = payload.to_url()
        provider = self._provider_factory()
        try:
            results = provider.search_lots(source_url)
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to fetch search results.") from exc
        finally:
            provider.close()
        return {"results": [self.serialize_result(item) for item in results], "source_url": source_url}

    def add_from_search(self, owner_user: dict, lot_url: str) -> dict:
        watchlist_service = self._watchlist_service_factory()
        return watchlist_service.add_tracked_lot(owner_user, lot_url)

    @staticmethod
    def serialize_result(item: CopartSearchResult) -> dict:
        return item.model_dump(mode="json")
