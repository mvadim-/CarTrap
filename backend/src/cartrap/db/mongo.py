"""MongoDB bootstrap helpers."""

from __future__ import annotations

from typing import Optional

from pymongo import MongoClient
from pymongo.database import Database


class MongoManager:
    """Small wrapper around MongoClient for app and worker reuse."""

    def __init__(self, uri: str, database_name: str, ping_on_startup: bool = False) -> None:
        self._uri = uri
        self._database_name = database_name
        self._ping_on_startup = ping_on_startup
        self._client: Optional[MongoClient] = None

    def connect(self) -> None:
        if self._client is not None:
            return

        self._client = MongoClient(self._uri, tz_aware=True)
        if self._ping_on_startup:
            self._client.admin.command("ping")

    @property
    def client(self) -> MongoClient:
        if self._client is None:
            raise RuntimeError("MongoDB client is not initialized.")
        return self._client

    @property
    def database(self) -> Database:
        return self.client[self._database_name]

    def close(self) -> None:
        if self._client is None:
            return
        self._client.close()
        self._client = None
