"""Router for NAS-hosted raw Copart proxy endpoints."""

from __future__ import annotations

import secrets
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from cartrap.modules.copart_gateway.schemas import (
    GatewayConnectorBootstrapRequest,
    GatewayConnectorExecutionResponse,
    GatewayConnectorExecuteLotDetailsRequest,
    GatewayConnectorExecuteSearchRequest,
    GatewayConnectorResponse,
    GatewayConnectorVerifyRequest,
    GatewayLotDetailsRequest,
    GatewaySearchCountRequest,
    GatewaySearchRequest,
)
from cartrap.modules.copart_gateway.service import CopartGatewayService, GatewayProxyResponse
from cartrap.modules.copart_provider.client import GATEWAY_ERROR_HEADER, GATEWAY_UPSTREAM_STATUS_HEADER
from cartrap.modules.copart_provider.errors import (
    CopartAuthenticationError,
    CopartChallengeError,
    CopartConfigurationError,
    CopartLoginRejectedError,
    CopartRateLimitError,
    CopartSessionInvalidError,
)


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


@router.post("/v1/connector/bootstrap", dependencies=[Depends(require_gateway_auth)], response_model=GatewayConnectorResponse)
def bootstrap_connector(
    payload: GatewayConnectorBootstrapRequest,
    service: CopartGatewayService = Depends(get_gateway_service),
):
    return _invoke_connector(
        lambda: service.bootstrap_connector(
            username=payload.username,
            password=payload.password,
            client_ip=payload.client_ip,
        )
    )


@router.post("/v1/connector/verify", dependencies=[Depends(require_gateway_auth)], response_model=GatewayConnectorExecutionResponse)
def verify_connector(
    payload: GatewayConnectorVerifyRequest,
    service: CopartGatewayService = Depends(get_gateway_service),
):
    return _invoke_connector(lambda: service.verify_connector(payload.session_bundle))


@router.post("/v1/connector/execute/search", dependencies=[Depends(require_gateway_auth)], response_model=GatewayConnectorExecutionResponse)
def execute_connector_search(
    payload: GatewayConnectorExecuteSearchRequest,
    service: CopartGatewayService = Depends(get_gateway_service),
):
    return _invoke_connector(
        lambda: service.execute_connector_search(payload.session_bundle, search_payload=payload.search_payload)
    )


@router.post("/v1/connector/execute/lot-details", dependencies=[Depends(require_gateway_auth)], response_model=GatewayConnectorExecutionResponse)
def execute_connector_lot_details(
    payload: GatewayConnectorExecuteLotDetailsRequest,
    service: CopartGatewayService = Depends(get_gateway_service),
    if_none_match: Optional[str] = Header(default=None),
):
    return _invoke_connector(
        lambda: service.execute_connector_lot_details(
            payload.session_bundle,
            lot_number=payload.lot_number,
            etag=if_none_match,
        )
    )


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


def _invoke_connector(operation):
    try:
        return operation()
    except CopartLoginRejectedError as exc:
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"detail": "Copart rejected connector bootstrap request."},
            headers={
                GATEWAY_ERROR_HEADER: "upstream_rejected",
                GATEWAY_UPSTREAM_STATUS_HEADER: str(exc.status_code or status.HTTP_403_FORBIDDEN),
            },
        )
    except CopartAuthenticationError:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Copart credentials were rejected."},
            headers={GATEWAY_ERROR_HEADER: "invalid_credentials"},
        )
    except CopartSessionInvalidError:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": "Copart session is no longer valid."},
            headers={GATEWAY_ERROR_HEADER: "auth_invalid"},
        )
    except CopartChallengeError:
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"detail": "Copart challenge replay failed."},
            headers={GATEWAY_ERROR_HEADER: "challenge_failed"},
        )
    except CopartRateLimitError:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"detail": "Copart connector bootstrap is rate limited."},
            headers={GATEWAY_ERROR_HEADER: "rate_limited"},
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
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"detail": str(exc)})
