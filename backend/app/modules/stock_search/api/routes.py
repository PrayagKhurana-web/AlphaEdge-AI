"""
API routes for the stock_search module.

This is the only file in the module that knows about HTTP status codes,
FastAPI's routing primitives, or how domain exceptions map to HTTP
responses. It contains no query validation logic of its own: `q` and
`limit` are passed through to SearchStocksService exactly as received (the
service owns all normalization, emptiness, length, and character
validation, per its own contract), and this handler's job is limited to
dependency resolution, converting the resulting StockSearchResults into a
StockSearchResponse, and translating any domain exception into a safe,
consistent error response -- per PROJECT_CONTEXT.md's Clean Architecture
rule that api/ is the only layer aware of HTTP.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.modules.stock_search.api.dependencies import get_search_stocks_service
from app.modules.stock_search.api.schemas import StockSearchResponse
from app.modules.stock_search.application.services import SearchStocksService
from app.modules.stock_search.domain.exceptions import (
    EmptySearchQueryError,
    InvalidSearchQueryError,
    InvalidSearchResultError,
    SearchProviderRateLimitedError,
    SearchProviderTimeoutError,
    SearchProviderUnavailableError,
    SearchQueryTooLongError,
    StockSearchError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/stocks", tags=["Stock Search"])

_SearchStocksServiceDep = Annotated[
    SearchStocksService, Depends(get_search_stocks_service)
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
    "/search",
    response_model=StockSearchResponse,
    summary="Search for Indian equities by symbol or company name",
    description=(
        "Searches NSE- and BSE-listed equities by a free-text query "
        "(symbol or company name) and returns matches in relevance order. "
        "Query validation (emptiness, length, allowed characters) and "
        "result-limit resolution are enforced by the underlying search "
        "service."
    ),
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "The search query is empty, too long, or contains unsupported characters."},
        status.HTTP_429_TOO_MANY_REQUESTS: {"description": "Upstream search provider rate limit exceeded."},
        status.HTTP_502_BAD_GATEWAY: {"description": "Upstream search provider returned unusable data."},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"description": "Upstream search provider is unreachable or down."},
        status.HTTP_504_GATEWAY_TIMEOUT: {"description": "Upstream search provider did not respond in time."},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Unexpected internal error."},
    },
)
async def search_stocks(
    service: _SearchStocksServiceDep,
    q: Annotated[str, Query(description="Free-text search query (symbol or company name).")],
    limit: Annotated[
        int | None,
        Query(description="Maximum number of results to return. Defaults to the service's configured default if omitted."),
    ] = None,
) -> StockSearchResponse:
    """
    Handles GET /api/v1/stocks/search.

    Delegates entirely to SearchStocksService for query validation, limit
    resolution, and search execution, and to StockSearchResponse.from_domain
    for response construction; this handler's own responsibility is
    limited to dependency resolution and exception-to-HTTP translation.
    """
    try:
        results = await service.search(q, limit=limit)
    except EmptySearchQueryError as exc:
        logger.warning("stock_search: empty search query rejected")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_error_detail(
                "EMPTY_SEARCH_QUERY",
                "Search query must not be empty.",
            ),
        ) from exc
    except SearchQueryTooLongError as exc:
        logger.warning(
            "stock_search: search query too long (length=%d, max=%d)",
            exc.query_length,
            exc.max_length,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_error_detail(
                "SEARCH_QUERY_TOO_LONG",
                "Search query is too long.",
            ),
        ) from exc
    except InvalidSearchQueryError as exc:
        logger.warning("stock_search: invalid search query rejected: %s", exc.reason)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_error_detail(
                "INVALID_SEARCH_QUERY",
                "Search query contains unsupported characters.",
            ),
        ) from exc
    except SearchProviderRateLimitedError as exc:
        logger.warning(
            "stock_search: provider rate limited (provider=%s, retry_after=%s)",
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
                "SEARCH_PROVIDER_RATE_LIMITED",
                "The search provider is currently rate-limiting requests. "
                "Please try again shortly.",
            ),
            headers=headers,
        ) from exc
    except SearchProviderTimeoutError as exc:
        logger.warning("stock_search: provider timeout (provider=%s)", exc.provider_name)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=_error_detail(
                "SEARCH_PROVIDER_TIMEOUT",
                "The search provider did not respond in time.",
            ),
        ) from exc
    except SearchProviderUnavailableError as exc:
        logger.warning("stock_search: provider unavailable (provider=%s)", exc.provider_name)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_error_detail(
                "SEARCH_PROVIDER_UNAVAILABLE",
                "The search provider is currently unavailable.",
            ),
        ) from exc
    except InvalidSearchResultError as exc:
        logger.warning("stock_search: invalid provider data (provider=%s)", exc.provider_name)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=_error_detail(
                "INVALID_SEARCH_RESULTS",
                "The search provider returned data that could not be used.",
            ),
        ) from exc
    except StockSearchError as exc:
        logger.exception("stock_search: unexpected domain error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_error_detail(
                "STOCK_SEARCH_ERROR",
                "An unexpected error occurred while searching for stocks.",
            ),
        ) from exc

    return StockSearchResponse.from_domain(results)