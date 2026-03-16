"""Service layer for NAS-hosted raw Copart proxy endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

import httpx

from cartrap.config import Settings, get_settings
from cartrap.modules.copart_provider.client import CopartHttpClient, CopartHttpPayloadResponse
from cartrap.modules.copart_provider.errors import CopartConfigurationError


@dataclass
class GatewayProxyResponse:
    payload: Optional[dict]
    etag: Optional[str]
    not_modified: bool = False


class CopartGatewayService:
    def __init__(
        self,
        settings: Optional[Settings] = None,
        client_factory: Optional[Callable[[], CopartHttpClient]] = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._client_factory = client_factory or self._build_default_client

    def proxy_search(self, payload: dict, etag: Optional[str] = None) -> GatewayProxyResponse:
        return self._to_gateway_response(self._call_client(lambda client: client.search_with_metadata(payload, etag=etag)))

    def proxy_search_count(self, payload: dict, etag: Optional[str] = None) -> GatewayProxyResponse:
        return self._to_gateway_response(
            self._call_client(lambda client: client.search_count_with_metadata(payload, etag=etag))
        )

    def proxy_lot_details(self, lot_number: int, etag: Optional[str] = None) -> GatewayProxyResponse:
        return self._to_gateway_response(
            self._call_client(lambda client: client.lot_details_with_metadata(str(lot_number), etag=etag))
        )

    def proxy_search_keywords(self) -> GatewayProxyResponse:
        payload = self._call_client(lambda client: client.search_keywords())
        return GatewayProxyResponse(payload=payload, etag=None, not_modified=False)

    def _build_default_client(self) -> CopartHttpClient:
        return CopartHttpClient(
            settings=self._settings.model_copy(
                update={
                    "copart_gateway_base_url": None,
                }
            )
        )

    @staticmethod
    def _to_gateway_response(response: CopartHttpPayloadResponse) -> GatewayProxyResponse:
        return GatewayProxyResponse(payload=response.payload, etag=response.etag, not_modified=response.not_modified)

    def _call_client(self, callback):
        client = self._client_factory()
        try:
            return callback(client)
        except httpx.HTTPStatusError:
            raise
        except CopartConfigurationError:
            raise
        finally:
            client.close()
