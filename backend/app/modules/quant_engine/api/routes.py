"""API routes for the quant_engine module.

Exposes the technical-analysis endpoint. This module owns HTTP routing,
OpenAPI documentation, and exception-to-HTTP translation only: the path
and query parameters are passed straight through to the application
service, domain exceptions raised by the service (including
stock_history's own domain exceptions, which may propagate unchanged
through quant_engine's historical-data adapter) are translated into
safe HTTP error responses, and the resulting domain object is converted
to its API response shape via
``TechnicalAnalysisSnapshotResponse.from_domain()``. No indicator
calculation, no infrastructure access, no service instantiation, and no
manual Decimal/JSON serialization happens here -- that mirrors the
approach used by ``stock_history/api/routes.py`` and
``company_fundamentals/api/routes.py``.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, status

from .dependencies import QuantEngineServiceDependency
from .schemas import TechnicalAnalysisSnapshotResponse
from ..domain.exceptions import (
    InsufficientHistoricalDataError,
    InvalidHistoricalDataError as InvalidQuantEngineHistoricalDataError,
    InvalidTechnicalAnalysisRequestError,
    TechnicalCalculationError,
)
from app.modules.stock_history.domain.exceptions import (
    HistoryProviderRateLimitedError,
    HistoryProviderTimeoutError,
    HistoryProviderUnavailableError,
    InvalidHistoricalDataError as InvalidStockHistoryDataError,
    InvalidHistoryRequestError,
)

router = APIRouter(
    prefix="/api/v1/stocks",
    tags=["Quant Engine"],
)


def _error_detail(code: str, message: str) -> dict[str, str]:
    """Build a safe, minimal error payload.

    Returns only a machine-readable ``code`` and a human-readable
    ``message``. Never includes raw exception text, provider payloads,
    stack traces, or other internal implementation details.
    """
    return {"code": code, "message": message}


@router.get(
    "/{display_symbol}/technical-analysis",
    response_model=TechnicalAnalysisSnapshotResponse,
    summary="Get a deterministic technical-analysis snapshot for a stock",
    response_description=(
        "The technical-analysis snapshot for the requested symbol, "
        "interval, and period."
    ),
    description=(
        "Returns a deterministic, rule-based technical-analysis "
        "snapshot calculated from historical OHLCV candle data: moving "
        "averages, momentum, volatility, volume, range, support and "
        "resistance, trend, and an overall signal.\n\n"
        "**Not financial advice**: `trend` and `signal` are mechanical "
        "interpretations of the calculated indicators, not predictions, "
        "forecasts, or financial recommendations.\n\n"
        "**Periods and intervals**: `period` and `interval` accept the "
        "same values as the historical-candle endpoint (e.g. `period` "
        "defaulting to `1y`, `interval` defaulting to `1d`); not every "
        "interval is available for every period.\n\n"
        "**Missing indicators**: any indicator whose lookback window "
        "isn't satisfied by the available candle history is returned as "
        "`null` rather than a fabricated value.\n\n"
        "**Decimal serialization**: numeric fields are serialized as "
        "exact strings to avoid floating-point precision loss.\n\n"
        "**Timestamps**: `latestCandleAt` and `calculatedAt` are "
        "timezone-aware.\n\n"
        "**Error handling**: domain errors raised while retrieving "
        "historical data or calculating the snapshot are translated "
        "into the HTTP responses documented below; the router itself "
        "performs no calculation or domain validation."
    ),
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "description": "Malformed or unsupported technical-analysis request.",
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": (
                "Not enough usable historical candles to calculate a "
                "reliable snapshot."
            ),
        },
        status.HTTP_429_TOO_MANY_REQUESTS: {
            "description": "The historical data provider rate-limited the request.",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "An unexpected failure occurred while calculating indicators.",
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
async def get_technical_analysis(
    quant_engine_service: QuantEngineServiceDependency,
    display_symbol: Annotated[
        str,
        Path(
            description="The display symbol of the stock to analyze.",
        ),
    ],
    interval: Annotated[
        str,
        Query(
            description="The candle granularity to use (e.g. '1d', '1h', '1wk').",
        ),
    ] = "1d",
    period: Annotated[
        str,
        Query(
            description="The historical range to use (e.g. '1y', '6mo', 'max').",
        ),
    ] = "1y",
) -> TechnicalAnalysisSnapshotResponse:
    """Fetch and return the technical-analysis snapshot for a stock symbol.

    Calls the quant_engine application service and translates any domain
    exceptions it raises -- including stock_history's own domain
    exceptions surfaced through quant_engine's historical-data adapter
    -- into safe HTTP error responses. No calculation or domain
    validation is duplicated here.
    """
    try:
        snapshot = await quant_engine_service.get_technical_analysis(
            display_symbol,
            interval=interval,
            period=period,
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
    except (InvalidTechnicalAnalysisRequestError, InvalidHistoryRequestError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_error_detail(
                "INVALID_TECHNICAL_ANALYSIS_REQUEST",
                "The requested symbol, interval, or period is invalid.",
            ),
        ) from exc
    except InsufficientHistoricalDataError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=_error_detail(
                "INSUFFICIENT_HISTORICAL_DATA",
                "Not enough usable historical candles are available to "
                "calculate a reliable technical-analysis snapshot "
                f"(available: {exc.available_candle_count}, "
                f"required: {exc.required_candle_count}).",
            ),
        ) from exc
    except (
        InvalidQuantEngineHistoricalDataError,
        InvalidStockHistoryDataError,
    ) as exc:
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
    except TechnicalCalculationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_error_detail(
                "TECHNICAL_CALCULATION_ERROR",
                "An unexpected error occurred while calculating the "
                "technical-analysis snapshot.",
            ),
        ) from exc

    return TechnicalAnalysisSnapshotResponse.from_domain(snapshot)