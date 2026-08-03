"""HTTP routes for Multibagger Potential."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, status

from app.modules.multibagger.api.dependencies import (
    MultibaggerPotentialServiceDependency,
    MultibaggerRankingServiceDependency,
)
from app.modules.multibagger.api.schemas import (
    MultibaggerPotentialResponse,
    MultibaggerRankingsResponse,
)
from app.modules.multibagger.domain.exceptions import (
    InvalidMultibaggerRequestError,
)


router = APIRouter(
    prefix="/api/v1/multibagger",
    tags=["Multibagger Potential"],
)


@router.get(
    "/rankings",
    response_model=MultibaggerRankingsResponse,
    summary="Get ranked Multibagger Potential candidates",
    description=(
        "Screens the configured universe using growth, financial "
        "strength, valuation, momentum and risk factors. Results "
        "are deterministic screening outputs, not guarantees."
    ),
)
async def get_multibagger_rankings(
    service: MultibaggerRankingServiceDependency,
    minimum_score: Annotated[
        int,
        Query(
            alias="minimumScore",
            ge=0,
            le=100,
        ),
    ] = 0,
    limit: Annotated[
        int,
        Query(ge=1, le=100),
    ] = 10,
    interval: Annotated[
        str,
        Query(),
    ] = "1d",
    technical_period: Annotated[
        str,
        Query(alias="technicalPeriod"),
    ] = "1y",
    financial_period: Annotated[
        str,
        Query(alias="financialPeriod"),
    ] = "annual",
) -> MultibaggerRankingsResponse:
    try:
        snapshot = await service.get_rankings(
            minimum_score=minimum_score,
            limit=limit,
            interval=interval,
            technical_period=technical_period,
            financial_period=financial_period,
        )
    except InvalidMultibaggerRequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_MULTIBAGGER_RANKING_REQUEST",
                "message": str(exc),
            },
        ) from exc

    return MultibaggerRankingsResponse.from_domain(
        snapshot
    )


@router.get(
    "/{display_symbol}",
    response_model=MultibaggerPotentialResponse,
    summary="Analyse one stock's Multibagger Potential",
)
async def get_multibagger_potential(
    service: MultibaggerPotentialServiceDependency,
    display_symbol: Annotated[
        str,
        Path(
            description=(
                "Stock symbol in SYMBOL.NSE or SYMBOL.BSE format."
            )
        ),
    ],
    interval: Annotated[
        str,
        Query(),
    ] = "1d",
    technical_period: Annotated[
        str,
        Query(alias="technicalPeriod"),
    ] = "1y",
    financial_period: Annotated[
        str,
        Query(alias="financialPeriod"),
    ] = "annual",
) -> MultibaggerPotentialResponse:
    try:
        snapshot = await service.analyse_stock(
            display_symbol,
            interval=interval,
            technical_period=technical_period,
            financial_period=financial_period,
        )
    except InvalidMultibaggerRequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_MULTIBAGGER_REQUEST",
                "message": str(exc),
            },
        ) from exc

    return MultibaggerPotentialResponse.from_domain(
        snapshot
    )
