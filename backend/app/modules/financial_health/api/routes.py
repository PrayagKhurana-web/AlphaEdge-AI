"""API routes for the financial_health module."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, status

from app.modules.financial_health.api.dependencies import (
    FinancialHealthServiceDependency,
)
from app.modules.financial_health.api.schemas import (
    FinancialHealthResponse,
)
from app.modules.financial_health.domain.exceptions import (
    FinancialHealthCalculationError,
    InsufficientFinancialHealthDataError,
    InvalidFinancialHealthDataError,
    InvalidFinancialHealthRequestError,
)
from app.modules.financial_statements.domain.exceptions import (
    FinancialStatementsProviderRateLimitedError,
    FinancialStatementsProviderTimeoutError,
    FinancialStatementsProviderUnavailableError,
    InvalidFinancialStatementsDataError,
    InvalidFinancialStatementsRequestError,
)


router = APIRouter(
    prefix="/api/v1/stocks",
    tags=["Financial Health"],
)


def _error_detail(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


@router.get(
    "/{display_symbol}/financial-health",
    response_model=FinancialHealthResponse,
    summary="Get deterministic financial-health analysis",
)
async def get_financial_health(
    financial_health_service: FinancialHealthServiceDependency,
    display_symbol: Annotated[
        str,
        Path(
            description=(
                "Stock display symbol using SYMBOL.EXCHANGE format."
            ),
        ),
    ],
    period: Annotated[
        str,
        Query(
            description="Reporting period: annual or quarterly.",
        ),
    ] = "annual",
) -> FinancialHealthResponse:
    try:
        snapshot = await financial_health_service.get_financial_health(
            display_symbol,
            period=period,
        )
    except (
        InvalidFinancialHealthRequestError,
        InvalidFinancialStatementsRequestError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_error_detail(
                "INVALID_FINANCIAL_HEALTH_REQUEST",
                "The requested symbol or reporting period is invalid.",
            ),
        ) from exc
    except (
        InsufficientFinancialHealthDataError,
        InvalidFinancialHealthDataError,
        InvalidFinancialStatementsDataError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=_error_detail(
                "INVALID_FINANCIAL_HEALTH_DATA",
                "Insufficient or unusable financial data was returned.",
            ),
        ) from exc
    except FinancialStatementsProviderRateLimitedError as exc:
        headers = (
            {"Retry-After": str(exc.retry_after_seconds)}
            if exc.retry_after_seconds is not None
            else None
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=_error_detail(
                "FINANCIAL_HEALTH_PROVIDER_RATE_LIMITED",
                "The financial data provider is rate-limiting requests.",
            ),
            headers=headers,
        ) from exc
    except FinancialStatementsProviderUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_error_detail(
                "FINANCIAL_HEALTH_PROVIDER_UNAVAILABLE",
                "The financial data provider is currently unavailable.",
            ),
        ) from exc
    except FinancialStatementsProviderTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=_error_detail(
                "FINANCIAL_HEALTH_PROVIDER_TIMEOUT",
                "The financial data provider timed out.",
            ),
        ) from exc
    except FinancialHealthCalculationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_error_detail(
                "FINANCIAL_HEALTH_CALCULATION_FAILED",
                "Financial-health analysis could not be calculated.",
            ),
        ) from exc

    return FinancialHealthResponse.from_domain(snapshot)
