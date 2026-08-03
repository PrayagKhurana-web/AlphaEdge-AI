"""Dependency wiring for Multibagger Potential."""

from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import Depends

from app.core.config import get_settings
from app.modules.company_fundamentals.api.dependencies import (
    get_company_fundamentals_service,
)
from app.modules.financial_health.api.dependencies import (
    get_financial_health_service,
)
from app.modules.multibagger.application.ranking_service import (
    MultibaggerRankingService,
)
from app.modules.multibagger.application.services import (
    MultibaggerPotentialService,
)
from app.modules.multibagger.infrastructure.adapters import (
    CompanyFundamentalsMultibaggerAdapter,
    FinancialHealthMultibaggerAdapter,
    StockAnalysisMultibaggerAdapter,
)
from app.modules.multibagger.infrastructure.calculators.multibagger_calculator import (
    MultibaggerPotentialCalculator,
)
from app.modules.stock_analysis.api.dependencies import (
    get_stock_analysis_service,
)


_potential_service: MultibaggerPotentialService | None = None
_ranking_service: MultibaggerRankingService | None = None

_potential_lock = asyncio.Lock()
_ranking_lock = asyncio.Lock()


async def get_multibagger_potential_service(
) -> MultibaggerPotentialService:
    global _potential_service

    if _potential_service is not None:
        return _potential_service

    async with _potential_lock:
        if _potential_service is not None:
            return _potential_service

        fundamentals_service = (
            await get_company_fundamentals_service()
        )
        financial_service = (
            await get_financial_health_service()
        )
        stock_analysis_service = (
            await get_stock_analysis_service()
        )

        _potential_service = MultibaggerPotentialService(
            fundamentals_provider=(
                CompanyFundamentalsMultibaggerAdapter(
                    fundamentals_service
                )
            ),
            financial_health_provider=(
                FinancialHealthMultibaggerAdapter(
                    financial_service
                )
            ),
            stock_analysis_provider=(
                StockAnalysisMultibaggerAdapter(
                    stock_analysis_service
                )
            ),
            calculator=MultibaggerPotentialCalculator(),
        )

        return _potential_service


async def get_multibagger_ranking_service(
) -> MultibaggerRankingService:
    global _ranking_service

    if _ranking_service is not None:
        return _ranking_service

    async with _ranking_lock:
        if _ranking_service is not None:
            return _ranking_service

        potential_service = (
            await get_multibagger_potential_service()
        )
        settings = get_settings()

        universe = tuple(
            symbol.strip().upper()
            for symbol in (
                settings.stock_analysis_top_picks_universe
            ).split(",")
            if symbol.strip()
        )

        _ranking_service = MultibaggerRankingService(
            potential_service=potential_service,
            ranking_universe=universe,
            cache_ttl_seconds=(
                settings
                .stock_analysis_top_picks_cache_ttl_seconds
            ),
            max_concurrency=(
                settings
                .stock_analysis_top_picks_max_concurrency
            ),
        )

        return _ranking_service


MultibaggerPotentialServiceDependency = Annotated[
    MultibaggerPotentialService,
    Depends(get_multibagger_potential_service),
]

MultibaggerRankingServiceDependency = Annotated[
    MultibaggerRankingService,
    Depends(get_multibagger_ranking_service),
]
