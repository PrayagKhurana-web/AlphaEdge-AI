"""
Dependency injection wiring for the stock_search module.

This file is the composition point where the concrete
YahooStockSearchProvider implementation is bound to StockSearchProviderPort
and assembled into the single SearchStocksService instance that
api/routes.py depends on. No route handler should ever import
YahooStockSearchProvider directly -- it depends only on the service
returned by get_search_stocks_service() below, per PROJECT_CONTEXT.md's
Clean Architecture dependency rule.

This module owns its own dedicated httpx.AsyncClient rather than reusing
market_data's shared client: market_data's dependency wiring keeps its
AsyncClient as private module state with no public accessor, and reaching
into another module's private internals would violate the module
isolation PROJECT_CONTEXT.md establishes. A single, application-wide
shared HTTP client owner is a reasonable future refactor, but it is a
cross-module change out of scope for this file.

request_timeout_seconds, max_query_length, default_limit, and max_limit
are read from the application's central Settings
(app.core.config.get_settings()) rather than hardcoded here, so they can
be overridden per environment via STOCK_SEARCH_REQUEST_TIMEOUT_SECONDS /
STOCK_SEARCH_MAX_QUERY_LENGTH / STOCK_SEARCH_DEFAULT_LIMIT /
STOCK_SEARCH_MAX_LIMIT environment variables.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from app.core.config import get_settings
from app.modules.stock_search.application.ports import StockSearchProviderPort
from app.modules.stock_search.application.services import SearchStocksService
from app.modules.stock_search.infrastructure.providers.yahoo_search_provider import (
    YahooStockSearchProvider,
)

# Module-level singleton state. Created at most once per process and
# reused across every request, so the underlying HTTP connection pool is
# actually reused rather than reconstructed per request.
_http_client: httpx.AsyncClient | None = None
_provider: StockSearchProviderPort | None = None
_service: SearchStocksService | None = None

# Guards both initialization and shutdown of the singletons above, so
# startup/first-request construction can never race against a shutdown
# call, and concurrent requests before initialization completes can never
# each construct their own AsyncClient/provider/service.
_init_lock = asyncio.Lock()


async def _get_or_create_service() -> SearchStocksService:
    """
    Returns the process-wide SearchStocksService singleton, constructing
    it (and its dependencies) on first call.

    Uses double-checked locking: the fast path (already initialized) never
    acquires the lock, and the lock is only taken for the one-time
    construction, so steady-state request handling incurs no lock
    contention. In normal operation this construction happens once, during
    stock_search_lifespan()'s startup phase, rather than lazily on the
    first request -- the lazy path remains as a safety net for any caller
    that resolves the dependency outside the lifespan-managed app.

    Settings are resolved via get_settings() (itself a singleton getter,
    so this does not re-parse environment variables on every call) once,
    inside the lock, at construction time.
    """
    global _http_client, _provider, _service

    if _service is not None:
        return _service

    async with _init_lock:
        if _service is not None:
            return _service

        settings = get_settings()

        _http_client = httpx.AsyncClient()
        _provider = YahooStockSearchProvider(
            http_client=_http_client,
            request_timeout_seconds=settings.stock_search_request_timeout_seconds,
        )
        _service = SearchStocksService(
            provider=_provider,
            max_query_length=settings.stock_search_max_query_length,
            default_limit=settings.stock_search_default_limit,
            max_limit=settings.stock_search_max_limit,
        )
        return _service


async def get_search_stocks_service() -> SearchStocksService:
    """
    FastAPI dependency that resolves to the shared SearchStocksService
    instance.

    Route handlers (api/routes.py) declare this as a dependency to obtain
    the service without knowing anything about how it, or the provider
    behind it, were constructed.
    """
    return await _get_or_create_service()


async def close_stock_search_dependencies() -> None:
    """
    Releases resources held by this module's singleton dependencies --
    specifically, closes the shared httpx.AsyncClient's connection pool.

    Idempotent and safe to call multiple times: the module-level
    reference is captured locally and cleared while holding `_init_lock`
    (so a concurrent initialization or a second, overlapping shutdown call
    cannot observe or act on a half-torn-down state), and the actual
    client close happens afterward, outside the lock, using only the
    locally captured reference. If the client was never constructed, or a
    prior call already closed and cleared it, this method does nothing.

    Any error raised by AsyncClient.aclose() is intentionally not caught
    here -- application shutdown should be able to observe and report a
    cleanup failure rather than have it silently suppressed.
    """
    global _http_client, _provider, _service

    async with _init_lock:
        client_to_close = _http_client
        _http_client = None
        _provider = None
        _service = None

    if client_to_close is not None:
        await client_to_close.aclose()


@asynccontextmanager
async def stock_search_lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    FastAPI lifespan context manager for the stock_search module.

    Composed into the application's overall lifespan in backend/app/main.py
    so that:
      - this module's shared AsyncClient/provider/service are constructed
        once during application startup, rather than lazily on the first
        request; and
      - the shared AsyncClient's connections are closed cleanly during
        application shutdown, rather than leaking when the process exits.

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
        await close_stock_search_dependencies()