"""API routes for the financial_statements module."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, status

from app.modules.financial_statements.api.dependencies import (
    FinancialStatementsServiceDependency,
)
from app.modules.financial_statements.api.schemas import (
    FinancialStatementsResponse,
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
    tags=["Financial Statements"],
)


def _error_detail(code: str, message: str) -> dict[str, str]:
    """Build a safe API error payload."""

    return {"code": code, "message": message}


@router.get(
    "/{display_symbol}/financial-statements",
    response_model=FinancialStatementsResponse,
    summary="Get company financial statements",
    response_description=(
        "Annual or quarterly financial statements for the requested stock."
    ),
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "description": "Malformed or unsupported financial-statements request.",
        },
        status.HTTP_429_TOO_MANY_REQUESTS: {
            "description": "The provider rate-limited the request.",
        },
        status.HTTP_502_BAD_GATEWAY: {
            "description": "The provider returned unusable statement data.",
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "The financial-statements provider is unavailable.",
        },
        status.HTTP_504_GATEWAY_TIMEOUT: {
            "description": "The financial-statements provider timed out.",
        },
    },
)
async def get_financial_statements(
    financial_statements_service: FinancialStatementsServiceDependency,
    display_symbol: Annotated[
        str,
        Path(
            description=(
                "Stock display symbol using SYMBOL.EXCHANGE format, "
                "for example RELIANCE.NSE."
            ),
        ),
    ],
    period: Annotated[
        str,
        Query(
            description="Reporting period: annual or quarterly.",
        ),
    ] = "annual",
) -> FinancialStatementsResponse:
    """Fetch annual or quarterly financial statements for a stock."""

    try:
        financial_statements = (
            await financial_statements_service.get_financial_statements(
                display_symbol,
                period=period,
            )
        )
    except FinancialStatementsProviderRateLimitedError as exc:
        headers = (
            {"Retry-After": str(exc.retry_after_seconds)}
            if exc.retry_after_seconds is not None
            else None
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=_error_detail(
                "FINANCIAL_STATEMENTS_PROVIDER_RATE_LIMITED",
                "The financial-statements provider is rate-limiting requests. "
                "Please retry shortly.",
            ),
            headers=headers,
        ) from exc
    except InvalidFinancialStatementsRequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_error_detail(
                "INVALID_FINANCIAL_STATEMENTS_REQUEST",
                "The requested symbol or reporting period is invalid.",
            ),
        ) from exc
    except InvalidFinancialStatementsDataError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=_error_detail(
                "INVALID_FINANCIAL_STATEMENTS_DATA",
                "The provider returned unusable financial-statement data.",
            ),
        ) from exc
    except FinancialStatementsProviderUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_error_detail(
                "FINANCIAL_STATEMENTS_PROVIDER_UNAVAILABLE",
                "The financial-statements provider is currently unavailable.",
            ),
        ) from exc
    except FinancialStatementsProviderTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=_error_detail(
                "FINANCIAL_STATEMENTS_PROVIDER_TIMEOUT",
                "The financial-statements provider timed out.",
            ),
        ) from exc

    return FinancialStatementsResponse.from_domain(financial_statements)


