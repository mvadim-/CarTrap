"""Router for NAS-hosted raw Copart proxy endpoints."""

from __future__ import annotations

import secrets
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from cartrap.modules.copart_gateway.schemas import (
    GatewayLotDetailsRequest,
    GatewaySearchCountRequest,
    GatewaySearchRequest,
)
from cartrap.modules.copart_gateway.service import CopartGatewayService, GatewayProxyResponse
from cartrap.modules.copart_provider.client import GATEWAY_ERROR_HEADER, GATEWAY_UPSTREAM_STATUS_HEADER
from cartrap.modules.copart_provider.errors import CopartConfigurationError


router = APIRouter()
bearer_scheme = HTTPBearer(auto_error=False)


def get_gateway_service(request: Request) -> CopartGatewayService:
    factory = getattr(request.app.state, "gateway_service_factory", None)
    if factory is None:
        raise RuntimeError("Gateway service factory is not configured.")
    return factory()


def require_gateway_auth(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> None:
    expected_token = request.app.state.settings.copart_gateway_token
    if not expected_token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Gateway bearer token is not configured.",
        )
    if credentials is None or not secrets.compare_digest(credentials.credentials, expected_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid gateway token.")


@router.get("/health")
def healthcheck(request: Request) -> dict[str, str]:
    settings = request.app.state.settings
    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.environment,
    }


@router.post("/v1/search", dependencies=[Depends(require_gateway_auth)])
def proxy_search(
    payload: GatewaySearchRequest,
    service: CopartGatewayService = Depends(get_gateway_service),
    if_none_match: Optional[str] = Header(default=None),
):
    return _invoke_proxy(lambda: service.proxy_search(payload.root, etag=if_none_match))


@router.post("/v1/search-count", dependencies=[Depends(require_gateway_auth)])
def proxy_search_count(
    payload: GatewaySearchCountRequest,
    service: CopartGatewayService = Depends(get_gateway_service),
    if_none_match: Optional[str] = Header(default=None),
):
    return _invoke_proxy(lambda: service.proxy_search_count(payload.root, etag=if_none_match))


@router.post("/v1/lot-details", dependencies=[Depends(require_gateway_auth)])
def proxy_lot_details(
    payload: GatewayLotDetailsRequest,
    service: CopartGatewayService = Depends(get_gateway_service),
    if_none_match: Optional[str] = Header(default=None),
):
    return _invoke_proxy(lambda: service.proxy_lot_details(payload.lotNumber, etag=if_none_match))


@router.get("/v1/search-keywords", dependencies=[Depends(require_gateway_auth)])
def proxy_search_keywords(service: CopartGatewayService = Depends(get_gateway_service)):
    return _invoke_proxy(service.proxy_search_keywords)


def _build_proxy_response(response: GatewayProxyResponse) -> Response:
    headers: dict[str, str] = {}
    if response.etag:
        headers["etag"] = response.etag
    if response.not_modified:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=headers)
    return JSONResponse(content=response.payload or {}, headers=headers)

def _invoke_proxy(operation) -> Response:
    try:
        response = operation()
    except httpx.HTTPStatusError as exc:
        headers = {
            GATEWAY_ERROR_HEADER: "upstream_rejected",
            GATEWAY_UPSTREAM_STATUS_HEADER: str(exc.response.status_code),
        }
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"detail": "Copart upstream request failed."},
            headers=headers,
        )
    except httpx.HTTPError:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": "Copart upstream is unavailable."},
            headers={GATEWAY_ERROR_HEADER: "unavailable"},
        )
    except ValueError:
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"detail": "Copart upstream returned malformed JSON."},
            headers={GATEWAY_ERROR_HEADER: "malformed_response"},
        )
    except CopartConfigurationError as exc:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": str(exc)},
        )
    return _build_proxy_response(response)
