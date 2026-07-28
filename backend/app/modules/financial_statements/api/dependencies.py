"""FastAPI dependencies for the financial_statements module."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Annotated, AsyncIterator

import httpx
from fastapi import Depends, FastAPI

from app.core.config import get_settings
from app.modules.financial_statements.application.services import (
    FinancialStatementsService,
)
from app.modules.financial_statements.infrastructure.providers.yahoo_financial_statements_provider import (
    YahooFinancialStatementsProvider,
)


_http_client: httpx.AsyncClient | None = None
_provider: YahooFinancialStatementsProvider | None = None
_service: FinancialStatementsService | None = None
_initialisation_lock = asyncio.Lock()


async def _get_or_create_service() -> FinancialStatementsService:
    global _http_client, _provider, _service

    if _service is not None:
        return _service

    async with _initialisation_lock:
        if _service is not None:
            return _service

        settings = get_settings()

        _http_client = httpx.AsyncClient()
        _provider = YahooFinancialStatementsProvider(
            http_client=_http_client,
            request_timeout_seconds=(
                settings.financial_statements_request_timeout_seconds
            ),
        )
        _service = FinancialStatementsService(provider=_provider)

    return _service


async def get_financial_statements_service() -> FinancialStatementsService:
    """Return the process-wide financial-statements service."""

    return await _get_or_create_service()


FinancialStatementsServiceDependency = Annotated[
    FinancialStatementsService,
    Depends(get_financial_statements_service),
]


@asynccontextmanager
async def financial_statements_lifespan(
    app: FastAPI,
) -> AsyncIterator[None]:
    """Initialise and close financial-statements dependencies."""

    del app

    global _http_client, _provider, _service

    await _get_or_create_service()

    try:
        yield
    finally:
        if _http_client is not None:
            await _http_client.aclose()

        _http_client = None
        _provider = None
        _service = None


