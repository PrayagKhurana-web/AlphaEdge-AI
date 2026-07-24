"""FastAPI dependency wiring for the quant_engine module.

This module assembles the quant_engine dependency graph only:

    stock_history's HistoricalDataService (reused, not re-created)
        -> StockHistoryServiceAdapter   (satisfies HistoricalDataProviderPort)
        -> TechnicalAnalysisCalculator  (satisfies TechnicalAnalysisCalculatorPort)
        -> QuantEngineService

It contains no FastAPI routes, no API schemas, no technical calculation,
no Yahoo Finance code, and no business logic -- those live in the
application service, the calculator, the adapter, and the API layer
respectively. The application layer never instantiates infrastructure
itself; this file (part of the API layer) is where that instantiation
happens, matching the dependency direction used throughout the project
(API -> Application -> Ports -> Infrastructure).

Singleton/lazy-initialization pattern:
- ``StockHistoryServiceAdapter``, ``TechnicalAnalysisCalculator``, and
  ``QuantEngineService`` are each private, process-wide singletons,
  following the same double-checked-locking pattern used by
  company_fundamentals's dependency wiring.
- quant_engine does not own an ``httpx.AsyncClient`` of its own --
  historical data retrieval is entirely delegated to stock_history's own
  ``HistoricalDataService`` singleton, obtained via stock_history's own
  dependency getter rather than constructed here. Reusing that existing
  singleton, instead of creating a second ``HistoricalDataService``,
  means quant_engine never opens a second connection pool to the same
  upstream data source.
- ``TechnicalAnalysisCalculator`` is stateless (pure Decimal arithmetic,
  no per-request or mutable instance state), so a single shared instance
  is safe to reuse across concurrent requests and avoids needless
  reconstruction on every call.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI

from app.modules.stock_history.api.dependencies import get_historical_data_service
from app.modules.stock_history.application.services import HistoricalDataService
from ..application.services import QuantEngineService
from ..infrastructure.adapters.stock_history_adapter import StockHistoryServiceAdapter
from ..infrastructure.calculators.technical_analysis_calculator import (
    TechnicalAnalysisCalculator,
)

_stock_history_adapter: StockHistoryServiceAdapter | None = None
_calculator: TechnicalAnalysisCalculator | None = None
_service: QuantEngineService | None = None
_initialization_lock = asyncio.Lock()


async def _get_or_create_service() -> QuantEngineService:
    """Return the process-wide quant_engine service singleton.

    Uses double-checked locking: the fast path returns the already-built
    singleton with no lock contention, and only the first caller that
    finds it unbuilt pays the cost of acquiring ``_initialization_lock``
    and constructing it.

    Reuses stock_history's own ``HistoricalDataService`` singleton
    (obtained via stock_history's own dependency getter) rather than
    constructing a second one -- quant_engine never instantiates
    stock_history's infrastructure directly.
    """
    global _stock_history_adapter, _calculator, _service

    if _service is not None:
        return _service

    async with _initialization_lock:
        if _service is not None:
            return _service

        historical_data_service: HistoricalDataService = (
            await get_historical_data_service()
        )

        _stock_history_adapter = StockHistoryServiceAdapter(
            stock_history_service=historical_data_service
        )
        _calculator = TechnicalAnalysisCalculator()
        _service = QuantEngineService(
            historical_data_provider=_stock_history_adapter,
            technical_analysis_calculator=_calculator,
        )

        return _service


async def get_quant_engine_service() -> QuantEngineService:
    """FastAPI dependency returning the quant_engine service.

    Delegates entirely to ``_get_or_create_service``; this function
    exists as the stable dependency-injection entry point that routes
    depend on.
    """
    return await _get_or_create_service()


QuantEngineServiceDependency = Annotated[
    QuantEngineService,
    Depends(get_quant_engine_service),
]


async def close_quant_engine_dependencies() -> None:
    """Reset the module's singleton state.

    Idempotent: calling this when nothing has been initialized, or
    calling it more than once, is a no-op beyond the first call. There is
    no ``httpx.AsyncClient`` owned by this module to close -- the
    underlying HTTP client belongs entirely to stock_history's own
    dependency lifecycle, which manages its own shutdown independently.
    This function only releases quant_engine's own singleton references
    so a subsequent call can rebuild them.
    """
    global _stock_history_adapter, _calculator, _service

    async with _initialization_lock:
        _stock_history_adapter = None
        _calculator = None
        _service = None


@asynccontextmanager
async def quant_engine_lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan for the quant_engine module.

    Eagerly initializes the module's singleton adapter, calculator, and
    service before yielding control, and resets them in a ``finally``
    block on shutdown so cleanup runs even if startup after this point
    fails or the application is interrupted. This lifespan must be
    entered after stock_history's own lifespan, since it depends on
    stock_history's ``HistoricalDataService`` singleton already being
    available.
    """
    await _get_or_create_service()
    try:
        yield
    finally:
        await close_quant_engine_dependencies()