"""FastAPI dependency wiring for the financial_health module."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI

from app.modules.financial_health.application.services import (
    FinancialHealthService,
)
from app.modules.financial_health.infrastructure.adapters.financial_statements_adapter import (
    FinancialStatementsServiceAdapter,
)
from app.modules.financial_health.infrastructure.calculators.financial_health_calculator import (
    FinancialHealthCalculator,
)
from app.modules.financial_statements.api.dependencies import (
    get_financial_statements_service,
)
from app.modules.financial_statements.application.services import (
    FinancialStatementsService,
)


_financial_statements_adapter: FinancialStatementsServiceAdapter | None = None
_calculator: FinancialHealthCalculator | None = None
_service: FinancialHealthService | None = None
_initialization_lock = asyncio.Lock()


async def _get_or_create_service() -> FinancialHealthService:
    global _financial_statements_adapter, _calculator, _service

    if _service is not None:
        return _service

    async with _initialization_lock:
        if _service is not None:
            return _service

        financial_statements_service: FinancialStatementsService = (
            await get_financial_statements_service()
        )

        _financial_statements_adapter = FinancialStatementsServiceAdapter(
            financial_statements_service=financial_statements_service,
        )
        _calculator = FinancialHealthCalculator()
        _service = FinancialHealthService(
            financial_statements_provider=_financial_statements_adapter,
            financial_health_calculator=_calculator,
        )

        return _service


async def get_financial_health_service() -> FinancialHealthService:
    """Return the process-wide financial-health service."""

    return await _get_or_create_service()


FinancialHealthServiceDependency = Annotated[
    FinancialHealthService,
    Depends(get_financial_health_service),
]


async def close_financial_health_dependencies() -> None:
    """Reset financial-health singleton state."""

    global _financial_statements_adapter, _calculator, _service

    async with _initialization_lock:
        _financial_statements_adapter = None
        _calculator = None
        _service = None


@asynccontextmanager
async def financial_health_lifespan(
    app: FastAPI,
) -> AsyncIterator[None]:
    """Initialise and reset financial-health dependencies."""

    del app

    await _get_or_create_service()

    try:
        yield
    finally:
        await close_financial_health_dependencies()
