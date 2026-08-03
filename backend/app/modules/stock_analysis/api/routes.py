"""HTTP routes for explainable stock analysis."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, status

from app.modules.stock_analysis.api.dependencies import (
    StockAnalysisServiceDependency,
)
from app.modules.stock_analysis.api.schemas import (
    StockAnalysisResponse,
    TopPicksResponse,
)

router = APIRouter(
    prefix="/api/v1",
    tags=["Stock Analysis"],
)


@router.get(
    "/analysis/top-picks",
    response_model=TopPicksResponse,
    summary="Get ranked AlphaEdge Top Picks",
    description=(
        "Analyses the configured stock universe with bounded "
        "concurrency and returns a short-lived cached ranking. "
        "The output is deterministic and is not investment advice."
    ),
)
async def get_top_picks(
    service: StockAnalysisServiceDependency,
    interval: Annotated[
        str,
        Query(description="Technical candle interval."),
    ] = "1d",
    technical_period: Annotated[
        str,
        Query(alias="technicalPeriod"),
    ] = "1y",
    financial_period: Annotated[
        str,
        Query(alias="financialPeriod"),
    ] = "annual",
) -> TopPicksResponse:
    snapshot = await service.get_top_picks(
        interval=interval,
        technical_period=technical_period,
        financial_period=financial_period,
    )

    return TopPicksResponse.from_domain(snapshot)


@router.get(
    "/stocks/{display_symbol}/analysis",
    response_model=StockAnalysisResponse,
    summary="Get an explainable probability-based stock outlook",
    description=(
        "Combines deterministic technical analysis, financial-health "
        "scoring and market activity. Probabilities are score-derived "
        "interpretations, not statistical forecasts or guarantees."
    ),
)
async def get_stock_analysis(
    service: StockAnalysisServiceDependency,
    display_symbol: Annotated[
        str,
        Path(description="Stock symbol in SYMBOL.EXCHANGE format."),
    ],
    interval: Annotated[
        str,
        Query(description="Technical candle interval."),
    ] = "1d",
    technical_period: Annotated[
        str,
        Query(alias="technicalPeriod"),
    ] = "1y",
    financial_period: Annotated[
        str,
        Query(alias="financialPeriod"),
    ] = "annual",
) -> StockAnalysisResponse:
    try:
        snapshot = await service.get_stock_analysis(
            display_symbol,
            interval=interval,
            technical_period=technical_period,
            financial_period=financial_period,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_STOCK_ANALYSIS_REQUEST",
                "message": "The requested stock analysis is invalid.",
            },
        ) from exc

    return StockAnalysisResponse.from_domain(snapshot)
