"""Service layer for NAS-hosted raw Copart proxy endpoints."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from time import perf_counter
from typing import Callable, Optional

import httpx

from cartrap.config import Settings, get_settings
from cartrap.core.logging import make_log_extra, new_correlation_id
from cartrap.modules.copart_provider.client import CopartHttpClient, CopartHttpPayloadResponse
from cartrap.modules.copart_provider.errors import CopartConfigurationError


@dataclass
class GatewayProxyResponse:
    payload: Optional[dict]
    etag: Optional[str]
    not_modified: bool = False


logger = logging.getLogger(__name__)


class CopartGatewayService:
    def __init__(
        self,
        settings: Optional[Settings] = None,
        client_factory: Optional[Callable[[], CopartHttpClient]] = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._client_factory = client_factory or self._build_default_client

    def proxy_search(self, payload: dict, etag: Optional[str] = None) -> GatewayProxyResponse:
        return self._execute_proxy_call(
            operation="copart_gateway.proxy.search",
            callback=lambda client, correlation_id: client.search_with_metadata(
                payload,
                etag=etag,
                correlation_id=correlation_id,
            ),
        )

    def proxy_search_count(self, payload: dict, etag: Optional[str] = None) -> GatewayProxyResponse:
        return self._execute_proxy_call(
            operation="copart_gateway.proxy.search_count",
            callback=lambda client, correlation_id: client.search_count_with_metadata(
                payload,
                etag=etag,
                correlation_id=correlation_id,
            ),
        )

    def proxy_lot_details(self, lot_number: int, etag: Optional[str] = None) -> GatewayProxyResponse:
        return self._execute_proxy_call(
            operation="copart_gateway.proxy.lot_details",
            callback=lambda client, correlation_id: client.lot_details_with_metadata(
                str(lot_number),
                etag=etag,
                correlation_id=correlation_id,
            ),
            lot_number=lot_number,
        )

    def proxy_search_keywords(self) -> GatewayProxyResponse:
        return self._execute_proxy_call(
            operation="copart_gateway.proxy.search_keywords",
            callback=lambda client, correlation_id: client.search_keywords(correlation_id=correlation_id),
        )

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

    def _execute_proxy_call(self, *, operation: str, callback, **metadata) -> GatewayProxyResponse:
        correlation_id = new_correlation_id("gateway-proxy")
        started_at = perf_counter()
        logger.info(
            f"{operation}.start",
            extra=make_log_extra(
                f"{operation}.start",
                correlation_id=correlation_id,
                **metadata,
            ),
        )
        client = self._client_factory()
        try:
            response = callback(client, correlation_id)
        except httpx.HTTPStatusError:
            logger.exception(
                f"{operation}.failed",
                extra=make_log_extra(
                    f"{operation}.failed",
                    correlation_id=correlation_id,
                    duration_ms=round((perf_counter() - started_at) * 1000, 2),
                    failure_class="http_status_error",
                    **metadata,
                ),
            )
            raise
        except CopartConfigurationError:
            logger.exception(
                f"{operation}.failed",
                extra=make_log_extra(
                    f"{operation}.failed",
                    correlation_id=correlation_id,
                    duration_ms=round((perf_counter() - started_at) * 1000, 2),
                    failure_class="configuration_error",
                    **metadata,
                ),
            )
            raise
        finally:
            client.close()
        if isinstance(response, GatewayProxyResponse):
            gateway_response = response
        elif isinstance(response, CopartHttpPayloadResponse):
            gateway_response = self._to_gateway_response(response)
        else:
            gateway_response = GatewayProxyResponse(payload=response, etag=None, not_modified=False)
        logger.info(
            f"{operation}.success",
            extra=make_log_extra(
                f"{operation}.success",
                correlation_id=correlation_id,
                duration_ms=round((perf_counter() - started_at) * 1000, 2),
                not_modified=gateway_response.not_modified,
                has_etag=bool(gateway_response.etag),
                **metadata,
            ),
        )
        return gateway_response
