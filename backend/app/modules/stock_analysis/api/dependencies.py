"""Dependency wiring for stock_analysis."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI

from app.core.config import get_settings
from app.modules.financial_health.api.dependencies import (
    get_financial_health_service,
)
from app.modules.quant_engine.api.dependencies import (
    get_quant_engine_service,
)
from app.modules.stock_analysis.application.services import (
    StockAnalysisService,
)
from app.modules.stock_analysis.infrastructure.adapters import (
    FinancialHealthAnalysisAdapter,
    QuantEngineAnalysisAdapter,
)
from app.modules.stock_analysis.infrastructure.calculators.stock_analysis_calculator import (
    StockAnalysisCalculator,
)


_service: StockAnalysisService | None = None
_lock = asyncio.Lock()


async def get_stock_analysis_service() -> StockAnalysisService:
    global _service

    if _service is not None:
        return _service

    async with _lock:
        if _service is not None:
            return _service

        technical_service = await get_quant_engine_service()
        financial_service = await get_financial_health_service()

        settings = get_settings()

        top_picks_universe = tuple(
            symbol.strip().upper()
            for symbol in (
                settings.stock_analysis_top_picks_universe
            ).split(",")
            if symbol.strip()
        )

        _service = StockAnalysisService(
            technical_provider=QuantEngineAnalysisAdapter(
                technical_service
            ),
            financial_provider=FinancialHealthAnalysisAdapter(
                financial_service
            ),
            calculator=StockAnalysisCalculator(),
            top_picks_universe=top_picks_universe,
            top_picks_cache_ttl_seconds=(
                settings
                .stock_analysis_top_picks_cache_ttl_seconds
            ),
            top_picks_max_concurrency=(
                settings
                .stock_analysis_top_picks_max_concurrency
            ),
        )

        return _service


StockAnalysisServiceDependency = Annotated[
    StockAnalysisService,
    Depends(get_stock_analysis_service),
]


@asynccontextmanager
async def stock_analysis_lifespan(
    app: FastAPI,
) -> AsyncIterator[None]:
    del app

    await get_stock_analysis_service()

    try:
        yield
    finally:
        global _service

        async with _lock:
            _service = None
