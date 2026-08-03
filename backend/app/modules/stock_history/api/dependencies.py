"""Dependency injection wiring for the stock_history module.

This file is the composition point where the concrete
YahooHistoryProvider implementation is bound to the historical-data
provider port and assembled into the single HistoricalDataService
instance that api/routes.py depends on.

This module owns one shared httpx.AsyncClient for stock_history. The
client, provider, and service are initialized once per process and reused
across requests. Their lifecycle is managed by stock_history_lifespan(),
which is composed into the application's main lifespan in app/main.py.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

import httpx
from fastapi import Depends, FastAPI

from app.core.config import get_settings
from app.modules.stock_history.application.ports import (
    HistoricalDataProviderPort,
)
from app.modules.stock_history.application.services import HistoricalDataService
from app.modules.stock_history.infrastructure.providers.yahoo_history_provider import (
    YahooHistoryProvider,
)

_http_client: httpx.AsyncClient | None = None
_provider: HistoricalDataProviderPort | None = None
_service: HistoricalDataService | None = None

_initialization_lock = asyncio.Lock()


async def _get_or_create_service() -> HistoricalDataService:
    """Return the process-wide historical-data service singleton.

    Constructs the shared HTTP client, provider, and service on first use.
    Double-checked locking prevents duplicate construction when multiple
    requests attempt initialization concurrently.
    """
    global _http_client, _provider, _service

    if _service is not None:
        return _service

    async with _initialization_lock:
        if _service is not None:
            return _service

        settings = get_settings()

        _http_client = httpx.AsyncClient()
        _provider = YahooHistoryProvider(
            http_client=_http_client,
            request_timeout_seconds=(
                settings.stock_history_request_timeout_seconds
            ),
        )
        _service = HistoricalDataService(provider=_provider)

        return _service


async def get_historical_data_service() -> HistoricalDataService:
    """Resolve the shared HistoricalDataService instance."""
    return await _get_or_create_service()


HistoricalDataServiceDependency = Annotated[
    HistoricalDataService,
    Depends(get_historical_data_service),
]


async def close_stock_history_dependencies() -> None:
    """Close and clear this module's shared dependencies.

    This function is idempotent. The singleton references are cleared
    while holding the initialization lock, and the HTTP client is closed
    afterward.
    """
    global _http_client, _provider, _service

    async with _initialization_lock:
        client_to_close = _http_client

        _http_client = None
        _provider = None
        _service = None

    if client_to_close is not None:
        await client_to_close.aclose()


@asynccontextmanager
async def stock_history_lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage startup and shutdown for stock_history dependencies."""
    await _get_or_create_service()

    try:
        yield
    finally:
        await close_stock_history_dependencies()