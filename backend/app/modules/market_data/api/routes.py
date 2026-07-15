"""
API routes for the market_data module's live index tracking capability.

This is the only file in the module that knows about HTTP status codes,
FastAPI's routing primitives, or how domain exceptions map to HTTP
responses. It contains no business logic: it resolves the injected
GetMarketIndicesSnapshotService, calls it, converts the resulting
MarketIndicesSnapshot into a MarketIndicesResponse, and translates any
domain exception into a safe, consistent error response -- per
PROJECT_CONTEXT.md's Clean Architecture rule that api/ is the only layer
aware of HTTP.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.modules.market_data.api.dependencies import (
    get_market_indices_snapshot_service,
)
from app.modules.market_data.api.schemas import MarketIndicesResponse
from app.modules.market_data.application.services import (
    GetMarketIndicesSnapshotService,
)
from app.modules.market_data.domain.exceptions import (
    InvalidQuoteDataError,
    MarketDataError,
    ProviderRateLimitedError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    SymbolNotFoundError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/market", tags=["Market Data"])

_MarketIndicesService = Annotated[
    GetMarketIndicesSnapshotService, Depends(get_market_indices_snapshot_service)
]


def _error_detail(code: str, message: str) -> dict[str, str]:
    """
    Builds the consistent error detail body used by every HTTPException
    raised from this router: {"code": ..., "message": ...}. Never includes
    raw exception text, provider payloads, or anything beyond a safe,
    user-facing message.
    """
    return {"code": code, "message": message}


@router.get(
    "/indices",
    response_model=MarketIndicesResponse,
    response_model_exclude_none=True,
    summary="Get live NIFTY 50, SENSEX, BANK NIFTY, and INDIA VIX quotes",
    description=(
        "Returns the current snapshot of India's key market indices "
        "(NIFTY 50, SENSEX, BANK NIFTY, INDIA VIX), served from a short-"
        "lived cache when available and refreshed from the upstream "
        "provider on a cache miss. Any index whose data is temporarily "
        "unavailable is omitted from the response rather than returned "
        "as null."
    ),
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "Unsupported/unknown index symbol."},
        status.HTTP_429_TOO_MANY_REQUESTS: {"description": "Upstream provider rate limit exceeded."},
        status.HTTP_502_BAD_GATEWAY: {"description": "Upstream provider returned unusable data."},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"description": "Upstream provider is unreachable or down."},
        status.HTTP_504_GATEWAY_TIMEOUT: {"description": "Upstream provider did not respond in time."},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Unexpected internal error."},
    },
)
async def get_market_indices(
    service: _MarketIndicesService,
) -> MarketIndicesResponse:
    """
    Handles GET /api/v1/market/indices.

    Delegates entirely to GetMarketIndicesSnapshotService for data
    retrieval and to MarketIndicesResponse.from_domain for response
    construction; this handler's own responsibility is limited to
    dependency resolution and exception-to-HTTP translation.
    """
    try:
        snapshot = await service.get_market_indices_snapshot()
    except SymbolNotFoundError as exc:
        logger.warning("market_data: unsupported index symbol requested: %s", exc.symbol)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_error_detail(
                "SYMBOL_NOT_FOUND",
                "One of the requested market indices is not supported.",
            ),
        ) from exc
    except ProviderRateLimitedError as exc:
        logger.warning(
            "market_data: provider rate limited (provider=%s, retry_after=%s)",
            exc.provider_name,
            exc.retry_after_seconds,
        )
        headers = (
            {"Retry-After": str(exc.retry_after_seconds)}
            if exc.retry_after_seconds is not None
            else None
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=_error_detail(
                "PROVIDER_RATE_LIMITED",
                "The market data provider is currently rate-limiting requests. "
                "Please try again shortly.",
            ),
            headers=headers,
        ) from exc
    except ProviderTimeoutError as exc:
        logger.warning("market_data: provider timeout (provider=%s)", exc.provider_name)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=_error_detail(
                "PROVIDER_TIMEOUT",
                "The market data provider did not respond in time.",
            ),
        ) from exc
    except ProviderUnavailableError as exc:
        logger.warning("market_data: provider unavailable (provider=%s)", exc.provider_name)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_error_detail(
                "PROVIDER_UNAVAILABLE",
                "The market data provider is currently unavailable.",
            ),
        ) from exc
    except InvalidQuoteDataError as exc:
        logger.warning("market_data: invalid provider data (provider=%s)", exc.provider_name)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=_error_detail(
                "INVALID_PROVIDER_DATA",
                "The market data provider returned data that could not be used.",
            ),
        ) from exc
    except MarketDataError as exc:
        logger.exception("market_data: unexpected domain error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_error_detail(
                "MARKET_DATA_ERROR",
                "An unexpected error occurred while fetching market data.",
            ),
        ) from exc

    return MarketIndicesResponse.from_domain(snapshot)