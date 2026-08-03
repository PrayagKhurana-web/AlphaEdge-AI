"""
Dependency injection wiring for the stock_details module.

This file is the composition point where the concrete YahooQuoteProvider
implementation is bound to StockQuoteProviderPort and assembled into the
single StockQuoteService instance that api/routes.py depends on. No route
handler should ever import YahooQuoteProvider directly -- it depends only
on the service returned by get_stock_quote_service() below, per
PROJECT_CONTEXT.md's Clean Architecture dependency rule.

This module owns one shared httpx.AsyncClient for stock_details,
lazily initialized on first use and eagerly initialized during
application startup via stock_details_lifespan(). This intentionally
matches the exact pattern already used by market_data/api/dependencies.py
and stock_search/api/dependencies.py: each module owns its own private
module-level singleton client/provider/service, guarded by its own
asyncio.Lock, rather than sharing a client via request.app.state or any
other cross-module mechanism. main.py composes stock_details_lifespan
alongside the other two modules' lifespans in a later integration step.

request_timeout_seconds is expected to be read from
settings.stock_details_request_timeout_seconds, a field a future
integration step will add to app.core.config.Settings -- this file does
not modify config.py itself.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

import httpx
from fastapi import Depends, FastAPI

from app.core.config import get_settings
from app.modules.stock_details.application.ports import StockQuoteProviderPort
from app.modules.stock_details.application.services import StockQuoteService
from app.modules.stock_details.infrastructure.providers.yahoo_quote_provider import (
    YahooQuoteProvider,
)

# Module-level singleton state. Created at most once per process and
# reused across every request, so the underlying HTTP connection pool is
# actually reused rather than reconstructed per request.
_http_client: httpx.AsyncClient | None = None
_provider: StockQuoteProviderPort | None = None
_service: StockQuoteService | None = None

# Guards both initialization and shutdown of the singletons above, so
# startup/first-request construction can never race against a shutdown
# call, and concurrent requests before initialization completes can never
# each construct their own AsyncClient/provider/service.
_initialization_lock = asyncio.Lock()


async def _get_or_create_service() -> StockQuoteService:
    """
    Returns the process-wide StockQuoteService singleton, constructing it
    (and its dependencies) on first call.

    Uses double-checked locking: the fast path (already initialized) never
    acquires the lock, and the lock is only taken for the one-time
    construction, so steady-state request handling incurs no lock
    contention. In normal operation this construction happens once, during
    stock_details_lifespan()'s startup phase, rather than lazily on the
    first request -- the lazy path remains as a safety net for any caller
    that resolves the dependency outside the lifespan-managed app.

    Settings are resolved via get_settings() (itself a singleton getter,
    so this does not re-parse environment variables on every call) once,
    inside the lock, at construction time.
    """
    global _http_client, _provider, _service

    if _service is not None:
        return _service

    async with _initialization_lock:
        if _service is not None:
            return _service

        settings = get_settings()

        _http_client = httpx.AsyncClient()
        _provider = YahooQuoteProvider(
            http_client=_http_client,
            request_timeout_seconds=settings.stock_details_request_timeout_seconds,
        )
        _service = StockQuoteService(provider=_provider)
        return _service


async def get_stock_quote_service() -> StockQuoteService:
    """
    FastAPI dependency that resolves to the shared StockQuoteService
    instance.

    Route handlers (api/routes.py) declare this as a dependency to obtain
    the service without knowing anything about how it, or the provider
    behind it, were constructed.
    """
    return await _get_or_create_service()


StockQuoteServiceDependency = Annotated[
    StockQuoteService, Depends(get_stock_quote_service)
]


async def close_stock_details_dependencies() -> None:
    """
    Releases resources held by this module's singleton dependencies --
    specifically, closes the shared httpx.AsyncClient's connection pool.

    Idempotent and safe to call multiple times: the module-level
    reference is captured locally and cleared while holding
    `_initialization_lock` (so a concurrent initialization or a second,
    overlapping shutdown call cannot observe or act on a half-torn-down
    state), and the actual client close happens afterward, outside the
    lock, using only the locally captured reference. If the client was
    never constructed, or a prior call already closed and cleared it,
    this method does nothing.

    Any error raised by AsyncClient.aclose() is intentionally not caught
    here -- application shutdown should be able to observe and report a
    cleanup failure rather than have it silently suppressed.
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
async def stock_details_lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    FastAPI lifespan context manager for the stock_details module.

    Intended to be composed into the application's overall lifespan in
    backend/app/main.py (a main.py-level change out of scope for this
    file) so that:
      - this module's shared AsyncClient/provider/service are constructed
        once during application startup, rather than lazily on the first
        request; and
      - the shared AsyncClient's connections are closed cleanly during
        application shutdown, rather than leaking when the process exits.

    This module owns exactly one shared AsyncClient for stock_details,
    separate from market_data's and stock_search's own shared clients --
    each module manages its own client lifecycle independently, and this
    lifespan never touches another module's resources.

    The `app` parameter is part of FastAPI's lifespan signature but is not
    used by this module (it has no need to read or mutate application
    state on the FastAPI instance itself) -- it is accepted, not renamed
    to a private/underscore form, to keep the signature self-documenting
    for whoever wires this into main.py.
    """
    await _get_or_create_service()
    try:
        yield
    finally:
        await close_stock_details_dependencies()