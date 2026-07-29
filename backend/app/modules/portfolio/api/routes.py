from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, status

from app.modules.auth.api.dependencies import (
    VerifiedCurrentUserDependency,
)

from app.modules.portfolio.api.dependencies import (
    PortfolioServiceDependency,
)
from app.modules.portfolio.api.schemas import (
    AddPortfolioHoldingRequest,
    PortfolioHoldingResponse,
    PortfolioResponse,
    UpdatePortfolioHoldingRequest,
)
from app.modules.portfolio.domain.exceptions import (
    InvalidPortfolioHoldingError,
    PortfolioHoldingAlreadyExistsError,
    PortfolioHoldingNotFoundError,
)
from app.modules.stock_details.domain.exceptions import (
    InvalidDisplaySymbolError,
    InvalidQuoteDataError,
    QuoteProviderRateLimitedError,
    QuoteProviderTimeoutError,
    QuoteProviderUnavailableError,
)


router = APIRouter(
    prefix="/api/v1/portfolio",
    tags=["Portfolio"],
)



def _error_detail(code: str, message: str) -> dict[str, str]:
    return {
        "code": code,
        "message": message,
    }


def _raise_quote_error(error: Exception) -> None:
    if isinstance(error, InvalidDisplaySymbolError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_error_detail(
                "INVALID_DISPLAY_SYMBOL",
                "The provided stock symbol is malformed.",
            ),
        ) from error

    if isinstance(error, QuoteProviderRateLimitedError):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=_error_detail(
                "QUOTE_PROVIDER_RATE_LIMITED",
                "The quote provider is rate-limiting requests.",
            ),
        ) from error

    if isinstance(error, QuoteProviderTimeoutError):
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=_error_detail(
                "QUOTE_PROVIDER_TIMEOUT",
                "The quote provider did not respond in time.",
            ),
        ) from error

    if isinstance(error, QuoteProviderUnavailableError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_error_detail(
                "QUOTE_PROVIDER_UNAVAILABLE",
                "The quote provider is currently unavailable.",
            ),
        ) from error

    if isinstance(error, InvalidQuoteDataError):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=_error_detail(
                "INVALID_QUOTE_DATA",
                "The quote provider returned unusable data.",
            ),
        ) from error

    raise error


@router.get(
    "",
    response_model=PortfolioResponse,
    summary="Get the current user's portfolio valuation",
)
async def get_portfolio(
    portfolio_service: PortfolioServiceDependency,
    current_user: VerifiedCurrentUserDependency,
) -> PortfolioResponse:
    try:
        valuation = await portfolio_service.value_portfolio(
            current_user.id
        )
    except (
        InvalidDisplaySymbolError,
        QuoteProviderRateLimitedError,
        QuoteProviderTimeoutError,
        QuoteProviderUnavailableError,
        InvalidQuoteDataError,
    ) as error:
        _raise_quote_error(error)
        raise

    return PortfolioResponse.from_domain(valuation)


@router.post(
    "",
    response_model=PortfolioHoldingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a holding to the current user's portfolio",
)
async def add_portfolio_holding(
    payload: AddPortfolioHoldingRequest,
    portfolio_service: PortfolioServiceDependency,
    current_user: VerifiedCurrentUserDependency,
) -> PortfolioHoldingResponse:
    try:
        holding = await portfolio_service.add_holding(
            user_id=current_user.id,
            display_symbol=payload.display_symbol,
            quantity=payload.quantity,
            average_buy_price=payload.average_buy_price,
        )
    except InvalidPortfolioHoldingError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_error_detail(
                "INVALID_PORTFOLIO_HOLDING",
                str(error),
            ),
        ) from error
    except PortfolioHoldingAlreadyExistsError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_error_detail(
                "PORTFOLIO_HOLDING_ALREADY_EXISTS",
                str(error),
            ),
        ) from error
    except (
        InvalidDisplaySymbolError,
        QuoteProviderRateLimitedError,
        QuoteProviderTimeoutError,
        QuoteProviderUnavailableError,
        InvalidQuoteDataError,
    ) as error:
        _raise_quote_error(error)
        raise

    return PortfolioHoldingResponse.from_domain(holding)


@router.put(
    "/{display_symbol}",
    response_model=PortfolioHoldingResponse,
    summary="Update quantity and average price for a holding",
)
async def update_portfolio_holding(
    payload: UpdatePortfolioHoldingRequest,
    portfolio_service: PortfolioServiceDependency,
    current_user: VerifiedCurrentUserDependency,
    display_symbol: Annotated[
        str,
        Path(min_length=5, max_length=32),
    ],
) -> PortfolioHoldingResponse:
    try:
        holding = await portfolio_service.update_holding(
            user_id=current_user.id,
            display_symbol=display_symbol,
            quantity=payload.quantity,
            average_buy_price=payload.average_buy_price,
        )
    except InvalidPortfolioHoldingError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_error_detail(
                "INVALID_PORTFOLIO_HOLDING",
                str(error),
            ),
        ) from error
    except PortfolioHoldingNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_error_detail(
                "PORTFOLIO_HOLDING_NOT_FOUND",
                str(error),
            ),
        ) from error

    return PortfolioHoldingResponse.from_domain(holding)


@router.delete(
    "/{display_symbol}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a holding from the current user's portfolio",
)
async def delete_portfolio_holding(
    portfolio_service: PortfolioServiceDependency,
    current_user: VerifiedCurrentUserDependency,
    display_symbol: Annotated[
        str,
        Path(min_length=5, max_length=32),
    ],
) -> None:
    try:
        await portfolio_service.remove_holding(
            user_id=current_user.id,
            display_symbol=display_symbol,
        )
    except InvalidPortfolioHoldingError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_error_detail(
                "INVALID_PORTFOLIO_HOLDING",
                str(error),
            ),
        ) from error
    except PortfolioHoldingNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_error_detail(
                "PORTFOLIO_HOLDING_NOT_FOUND",
                str(error),
            ),
        ) from error
