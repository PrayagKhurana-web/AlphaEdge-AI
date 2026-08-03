"""API routes for the company_fundamentals module.

Exposes the company fundamentals endpoint. This module owns HTTP
routing, OpenAPI documentation, and exception-to-HTTP translation only:
the path parameter is passed straight through to the application
service, domain exceptions raised by the service are translated into
safe HTTP error responses, and the resulting domain object is converted
to its API response shape via
``CompanyFundamentalsResponse.from_domain()``. No business logic, domain
validation, or provider access happens here -- that mirrors the approach
used by ``stock_history/api/routes.py``.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, status

from .dependencies import CompanyFundamentalsServiceDependency
from .schemas import CompanyFundamentalsResponse
from ..domain.exceptions import (
    FundamentalsProviderRateLimitedError,
    FundamentalsProviderTimeoutError,
    FundamentalsProviderUnavailableError,
    InvalidFundamentalsDataError,
    InvalidFundamentalsRequestError,
)

router = APIRouter(
    prefix="/api/v1/stocks",
    tags=["Company Fundamentals"],
)


def _error_detail(code: str, message: str) -> dict[str, str]:
    """Build a safe, minimal error payload.

    Returns only a machine-readable ``code`` and a human-readable
    ``message``. Never includes raw exception text, provider payloads,
    stack traces, or other internal implementation details.
    """
    return {"code": code, "message": message}


@router.get(
    "/{display_symbol}/fundamentals",
    response_model=CompanyFundamentalsResponse,
    summary="Get core company fundamentals for a stock",
    response_description=(
        "The core fundamentals snapshot for the requested symbol."
    ),
    description=(
        "Returns a point-in-time snapshot of a company's core "
        "fundamentals: identity, valuation, per-share and profitability "
        "metrics, growth, balance-sheet and income highlights, dividend "
        "figures, and trading reference values.\n\n"
        "**Nullability**: monetary and ratio fields may be unavailable "
        "for a given company and are returned as `null` rather than a "
        "fabricated value such as `0` or `\"N/A\"`.\n\n"
        "**Decimal serialization**: numeric fields are serialized as "
        "exact strings to avoid floating-point precision loss, and are "
        "passed through exactly as reported by the data provider -- no "
        "scaling, rounding, or unit conversion (e.g. to crores, lakhs, "
        "millions, or billions) is applied.\n\n"
        "**Timestamps**: `fetchedAt` is timezone-aware and reflects "
        "retrieval time, not necessarily the provider's underlying "
        "financial reporting date.\n\n"
        "**Error handling**: domain errors raised by the fundamentals "
        "service are translated into the HTTP responses documented "
        "below; the router itself performs no domain validation."
    ),
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "description": "Malformed or unsupported fundamentals request.",
        },
        status.HTTP_429_TOO_MANY_REQUESTS: {
            "description": "The fundamentals data provider rate-limited the request.",
        },
        status.HTTP_502_BAD_GATEWAY: {
            "description": "The fundamentals data provider returned unusable data.",
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "The fundamentals data provider is unavailable.",
        },
        status.HTTP_504_GATEWAY_TIMEOUT: {
            "description": "The fundamentals data provider timed out.",
        },
    },
)
async def get_company_fundamentals(
    company_fundamentals_service: CompanyFundamentalsServiceDependency,
    display_symbol: Annotated[
        str,
        Path(
            description="The display symbol of the stock to fetch fundamentals for.",
        ),
    ],
) -> CompanyFundamentalsResponse:
    """Fetch and return the core fundamentals snapshot for a stock symbol.

    Calls the company fundamentals service and translates any domain
    exceptions it raises into safe HTTP error responses. No domain
    validation is duplicated here.
    """
    try:
        fundamentals = await company_fundamentals_service.get_fundamentals(
            display_symbol
        )
    except FundamentalsProviderRateLimitedError as exc:
        headers = (
            {"Retry-After": str(exc.retry_after_seconds)}
            if exc.retry_after_seconds is not None
            else None
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=_error_detail(
                "FUNDAMENTALS_PROVIDER_RATE_LIMITED",
                "The fundamentals data provider is rate-limiting requests. "
                "Please retry shortly.",
            ),
            headers=headers,
        ) from exc
    except InvalidFundamentalsRequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_error_detail(
                "INVALID_FUNDAMENTALS_REQUEST",
                "The requested symbol is invalid.",
            ),
        ) from exc
    except InvalidFundamentalsDataError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=_error_detail(
                "INVALID_FUNDAMENTALS_DATA",
                "The fundamentals data provider returned unusable data.",
            ),
        ) from exc
    except FundamentalsProviderUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_error_detail(
                "FUNDAMENTALS_PROVIDER_UNAVAILABLE",
                "The fundamentals data provider is currently unavailable.",
            ),
        ) from exc
    except FundamentalsProviderTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=_error_detail(
                "FUNDAMENTALS_PROVIDER_TIMEOUT",
                "The fundamentals data provider timed out.",
            ),
        ) from exc

    return CompanyFundamentalsResponse.from_domain(fundamentals)