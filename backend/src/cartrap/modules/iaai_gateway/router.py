"""Router for NAS-hosted raw IAAI proxy endpoints."""

from __future__ import annotations

import secrets
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from cartrap.modules.iaai_gateway.schemas import (
    GatewayConnectorBootstrapRequest,
    GatewayConnectorExecutionResponse,
    GatewayConnectorExecuteLotDetailsRequest,
    GatewayConnectorExecuteSearchRequest,
    GatewayConnectorResponse,
    GatewayConnectorVerifyRequest,
    GatewayLotDetailsRequest,
    GatewaySearchRequest,
)
from cartrap.modules.iaai_gateway.service import GatewayProxyResponse, IaaiGatewayService
from cartrap.modules.iaai_provider.errors import (
    IaaiAuthenticationError,
    IaaiConfigurationError,
    IaaiRefreshError,
    IaaiSessionInvalidError,
    IaaiWafError,
)


router = APIRouter()
bearer_scheme = HTTPBearer(auto_error=False)
GATEWAY_ERROR_HEADER = "x-iaai-gateway-error"
GATEWAY_UPSTREAM_STATUS_HEADER = "x-iaai-upstream-status"


def get_gateway_service(request: Request) -> IaaiGatewayService:
    factory = getattr(request.app.state, "gateway_service_factory", None)
    if factory is None:
        raise RuntimeError("Gateway service factory is not configured.")
    return factory()


def require_gateway_auth(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> None:
    expected_token = request.app.state.settings.iaai_gateway_token
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
    service: IaaiGatewayService = Depends(get_gateway_service),
    if_none_match: Optional[str] = Header(default=None),
):
    return _invoke_proxy(lambda: service.proxy_search(payload.root, etag=if_none_match))


@router.post("/v1/lot-details", dependencies=[Depends(require_gateway_auth)])
def proxy_lot_details(
    payload: GatewayLotDetailsRequest,
    service: IaaiGatewayService = Depends(get_gateway_service),
    if_none_match: Optional[str] = Header(default=None),
):
    return _invoke_proxy(lambda: service.proxy_lot_details(payload.provider_lot_id, etag=if_none_match))


@router.post("/v1/connector/bootstrap", dependencies=[Depends(require_gateway_auth)], response_model=GatewayConnectorResponse)
def bootstrap_connector(
    payload: GatewayConnectorBootstrapRequest,
    service: IaaiGatewayService = Depends(get_gateway_service),
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
    service: IaaiGatewayService = Depends(get_gateway_service),
):
    return _invoke_connector(lambda: service.verify_connector(payload.session_bundle))


@router.post("/v1/connector/execute/search", dependencies=[Depends(require_gateway_auth)], response_model=GatewayConnectorExecutionResponse)
def execute_connector_search(
    payload: GatewayConnectorExecuteSearchRequest,
    service: IaaiGatewayService = Depends(get_gateway_service),
):
    return _invoke_connector(
        lambda: service.execute_connector_search(payload.session_bundle, search_payload=payload.search_payload)
    )


@router.post("/v1/connector/execute/lot-details", dependencies=[Depends(require_gateway_auth)], response_model=GatewayConnectorExecutionResponse)
def execute_connector_lot_details(
    payload: GatewayConnectorExecuteLotDetailsRequest,
    service: IaaiGatewayService = Depends(get_gateway_service),
    if_none_match: Optional[str] = Header(default=None),
):
    return _invoke_connector(
        lambda: service.execute_connector_lot_details(
            payload.session_bundle,
            provider_lot_id=payload.provider_lot_id,
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
    except IaaiWafError:
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"detail": "IAAI upstream request failed."},
            headers={
                GATEWAY_ERROR_HEADER: "upstream_rejected",
                GATEWAY_UPSTREAM_STATUS_HEADER: str(status.HTTP_403_FORBIDDEN),
            },
        )
    except httpx.HTTPStatusError as exc:
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"detail": "IAAI upstream request failed."},
            headers={
                GATEWAY_ERROR_HEADER: "upstream_rejected",
                GATEWAY_UPSTREAM_STATUS_HEADER: str(exc.response.status_code),
            },
        )
    except httpx.HTTPError:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": "IAAI upstream is unavailable."},
            headers={GATEWAY_ERROR_HEADER: "unavailable"},
        )
    except ValueError:
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"detail": "IAAI upstream returned malformed JSON."},
            headers={GATEWAY_ERROR_HEADER: "malformed_response"},
        )
    except IaaiConfigurationError as exc:
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"detail": str(exc)})
    return _build_proxy_response(response)


def _invoke_connector(operation):
    try:
        return operation()
    except IaaiWafError:
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"detail": "IAAI rejected connector bootstrap request."},
            headers={
                GATEWAY_ERROR_HEADER: "upstream_rejected",
                GATEWAY_UPSTREAM_STATUS_HEADER: str(status.HTTP_403_FORBIDDEN),
            },
        )
    except IaaiAuthenticationError:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "IAAI credentials were rejected."},
            headers={GATEWAY_ERROR_HEADER: "invalid_credentials"},
        )
    except (IaaiSessionInvalidError, IaaiRefreshError):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": "IAAI session is no longer valid."},
            headers={GATEWAY_ERROR_HEADER: "auth_invalid"},
        )
    except httpx.HTTPError:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": "IAAI upstream is unavailable."},
            headers={GATEWAY_ERROR_HEADER: "unavailable"},
        )
    except ValueError:
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"detail": "IAAI upstream returned malformed JSON."},
            headers={GATEWAY_ERROR_HEADER: "malformed_response"},
        )
    except IaaiConfigurationError as exc:
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"detail": str(exc)})
