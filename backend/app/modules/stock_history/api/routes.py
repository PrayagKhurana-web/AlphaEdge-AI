"""API routes for the stock_history module.

Exposes the historical stock candle endpoint. This module owns HTTP
routing, OpenAPI documentation, and exception-to-HTTP translation only:
request parameters are passed straight through to the application
service, domain exceptions raised by the service are translated into
safe HTTP error responses, and the resulting domain object is converted
to its API response shape via ``HistoricalSeriesResponse.from_domain()``.
No business logic, domain validation, or provider access happens here —
that mirrors the approach used by ``stock_details/api/routes.py``.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from .dependencies import get_historical_data_service
from .schemas import HistoricalSeriesResponse
from ..application.services import HistoricalDataService
from ..domain.exceptions import (
    HistoryProviderRateLimitedError,
    HistoryProviderTimeoutError,
    HistoryProviderUnavailableError,
    InvalidHistoricalDataError,
    InvalidHistoryRequestError,
)

router = APIRouter(
    prefix="/api/v1/stocks",
    tags=["Stock History"],
)


def _error_detail(code: str, message: str) -> dict[str, str]:
    """Build a safe, minimal error payload.

    Returns only a machine-readable ``code`` and a human-readable
    ``message``. Never includes raw exception text, provider payloads,
    stack traces, or other internal implementation details.
    """
    return {"code": code, "message": message}


@router.get(
    "/{display_symbol}/history",
    response_model=HistoricalSeriesResponse,
    summary="Get historical candle data for a stock",
    response_description=(
        "The historical candle series for the requested symbol, period, "
        "and interval."
    ),
    description=(
        "Returns historical OHLCV candle data for the given stock symbol.\n\n"
        "**Periods**: the `period` query parameter accepts the ranges "
        "supported by the underlying data provider (e.g. `1d`, `5d`, "
        "`1mo`, `3mo`, `6mo`, `1y`, `2y`, `5y`, `10y`, `ytd`, `max`), "
        "defaulting to `1y`.\n\n"
        "**Intervals**: the `interval` query parameter accepts the "
        "granularities supported by the underlying data provider (e.g. "
        "`1m`, `5m`, `15m`, `30m`, `1h`, `1d`, `1wk`, `1mo`), defaulting "
        "to `1d`. Not every interval is available for every period, and "
        "an unsupported period/interval combination is rejected as an "
        "invalid request.\n\n"
        "**Candle ordering**: candles are returned in the exact order "
        "provided by the data source. This endpoint never sorts, "
        "deduplicates, or recalculates values.\n\n"
        "**adjustedClose semantics**: `adjustedClose` reflects the "
        "close price adjusted for corporate actions such as splits and "
        "dividends. It may be `null` for a given candle when the "
        "provider does not supply an adjusted value.\n\n"
        "**Decimal serialization**: price fields (`open`, `high`, `low`, "
        "`close`, `adjustedClose`) are serialized as exact strings to "
        "avoid floating-point precision loss.\n\n"
        "**Timestamps**: `timestamp` and `fetchedAt` are timezone-aware "
        "datetimes.\n\n"
        "**Error handling**: domain errors raised by the historical data "
        "service are translated into the HTTP responses documented below; "
        "the router itself performs no domain validation."
    ),
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "description": "Malformed or unsupported history request.",
        },
        status.HTTP_429_TOO_MANY_REQUESTS: {
            "description": "The historical data provider rate-limited the request.",
        },
        status.HTTP_502_BAD_GATEWAY: {
            "description": "The historical data provider returned unusable data.",
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "The historical data provider is unavailable.",
        },
        status.HTTP_504_GATEWAY_TIMEOUT: {
            "description": "The historical data provider timed out.",
        },
    },
)
async def get_stock_history(
    historical_data_service: Annotated[
        HistoricalDataService,
        Depends(get_historical_data_service),
    ],
    display_symbol: Annotated[
        str,
        Path(
            description="The display symbol of the stock to fetch history for.",
        ),
    ],
    period: Annotated[
        str,
        Query(
            description="The historical range to fetch (e.g. '1y', '6mo', 'max').",
        ),
    ] = "1y",
    interval: Annotated[
        str,
        Query(
            description="The candle granularity to fetch (e.g. '1d', '1h', '1wk').",
        ),
    ] = "1d",
) -> HistoricalSeriesResponse:
    """Fetch and return the historical candle series for a stock symbol.

    Calls the historical data service and translates any domain
    exceptions it raises into safe HTTP error responses. No domain
    validation is duplicated here.
    """
    try:
        series = await historical_data_service.get_history(
            display_symbol,
            period=period,
            interval=interval,
        )
    except HistoryProviderRateLimitedError as exc:
        headers = (
            {"Retry-After": str(exc.retry_after_seconds)}
            if exc.retry_after_seconds is not None
            else None
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=_error_detail(
                "HISTORY_PROVIDER_RATE_LIMITED",
                "The historical data provider is rate-limiting requests. "
                "Please retry shortly.",
            ),
            headers=headers,
        ) from exc
    except InvalidHistoryRequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_error_detail(
                "INVALID_HISTORY_REQUEST",
                "The requested symbol, period, interval, or combination "
                "of period and interval is invalid.",
            ),
        ) from exc
    except InvalidHistoricalDataError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=_error_detail(
                "INVALID_HISTORICAL_DATA",
                "The historical data provider returned unusable data.",
            ),
        ) from exc
    except HistoryProviderUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_error_detail(
                "HISTORY_PROVIDER_UNAVAILABLE",
                "The historical data provider is currently unavailable.",
            ),
        ) from exc
    except HistoryProviderTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=_error_detail(
                "HISTORY_PROVIDER_TIMEOUT",
                "The historical data provider timed out.",
            ),
        ) from exc

    return HistoricalSeriesResponse.from_domain(series)