"""
API routes for the stock_details module.

This is the only file in the module that knows about HTTP status codes,
FastAPI's routing primitives, or how domain exceptions map to HTTP
responses. It contains no business logic: it resolves the injected
StockQuoteService, calls it, converts the resulting StockQuote into a
StockQuoteResponse, and translates each domain exception into a safe,
consistent HTTP response -- per PROJECT_CONTEXT.md's Clean Architecture
rule that api/ is the only layer aware of HTTP. The API layer is
responsible for this translation; application/services.py and the
provider never produce HTTP concepts themselves.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.modules.stock_details.api.dependencies import StockQuoteServiceDependency
from app.modules.stock_details.api.schemas import StockQuoteResponse
from app.modules.stock_details.domain.exceptions import (
    InvalidDisplaySymbolError,
    InvalidQuoteDataError,
    QuoteProviderRateLimitedError,
    QuoteProviderTimeoutError,
    QuoteProviderUnavailableError,
)

router = APIRouter(prefix="/api/v1/stocks", tags=["Stock Details"])


def _error_detail(code: str, message: str) -> dict[str, str]:
    """
    Builds the consistent error detail body used by every HTTPException
    raised from this router: {"code": ..., "message": ...}. Never includes
    raw exception text, provider payloads, stack traces, or anything
    beyond a safe, user-facing message.
    """
    return {"code": code, "message": message}


@router.get(
    "/{display_symbol}/quote",
    response_model=StockQuoteResponse,
    summary="Get the current quote for a single stock",
    description=(
        "Returns the current quote (price, change, day range, previous "
        "close) for the stock identified by `display_symbol`, in the "
        "form SYMBOL.EXCHANGE (e.g. RELIANCE.NSE, 500325.BSE)."
    ),
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "The display symbol is empty or malformed."},
        status.HTTP_429_TOO_MANY_REQUESTS: {"description": "Upstream quote provider rate limit exceeded."},
        status.HTTP_502_BAD_GATEWAY: {"description": "Upstream quote provider returned unusable data."},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"description": "Upstream quote provider is unreachable or down."},
        status.HTTP_504_GATEWAY_TIMEOUT: {"description": "Upstream quote provider did not respond in time."},
    },
)
async def get_stock_quote(
    display_symbol: str,
    service: StockQuoteServiceDependency,
) -> StockQuoteResponse:
    """
    Handles GET /api/v1/stocks/{display_symbol}/quote.

    Delegates entirely to StockQuoteService for display-symbol validation
    and quote retrieval, and to StockQuoteResponse.from_domain for
    response construction; this handler's own responsibility is limited
    to dependency resolution and exception-to-HTTP translation.
    """
    try:
        quote = await service.get_quote(display_symbol)
    except InvalidDisplaySymbolError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_error_detail(
                "INVALID_DISPLAY_SYMBOL",
                "The provided stock symbol is empty or malformed.",
            ),
        ) from exc
    except QuoteProviderRateLimitedError as exc:
        headers = (
            {"Retry-After": str(exc.retry_after_seconds)}
            if exc.retry_after_seconds is not None
            else None
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=_error_detail(
                "QUOTE_PROVIDER_RATE_LIMITED",
                "The quote provider is currently rate-limiting requests. "
                "Please try again shortly.",
            ),
            headers=headers,
        ) from exc
    except QuoteProviderTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=_error_detail(
                "QUOTE_PROVIDER_TIMEOUT",
                "The quote provider did not respond in time.",
            ),
        ) from exc
    except QuoteProviderUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_error_detail(
                "QUOTE_PROVIDER_UNAVAILABLE",
                "The quote provider is currently unavailable.",
            ),
        ) from exc
    except InvalidQuoteDataError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=_error_detail(
                "INVALID_QUOTE_DATA",
                "The quote provider returned data that could not be used.",
            ),
        ) from exc

    return StockQuoteResponse.from_domain(quote)