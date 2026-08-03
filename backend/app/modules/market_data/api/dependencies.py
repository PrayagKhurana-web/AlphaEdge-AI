"""
Dependency injection wiring for the market_data module's live index
tracking capability.

This file is the composition point where concrete infrastructure
implementations (YahooFinanceProvider, InMemoryMarketDataCache) are bound
to the application-layer ports they satisfy, and assembled into the single
GetMarketIndicesSnapshotService instance that api/routes.py depends on. No
route handler should ever import YahooFinanceProvider or
InMemoryMarketDataCache directly -- they depend only on the service
returned by get_market_indices_snapshot_service() below, per
PROJECT_CONTEXT.md's Clean Architecture dependency rule.

request_timeout_seconds and cache_ttl_seconds are read from the
application's central Settings (app.core.config.get_settings()) rather
than hardcoded here, so they can be overridden per environment via
MARKET_DATA_REQUEST_TIMEOUT_SECONDS / MARKET_DATA_CACHE_TTL_SECONDS
environment variables.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from app.core.config import get_settings
from app.modules.market_data.application.ports import (
    MarketDataCachePort,
    MarketDataProviderPort,
)
from app.modules.market_data.application.services import (
    GetMarketIndicesSnapshotService,
)
from app.modules.market_data.infrastructure.cache import InMemoryMarketDataCache
from app.modules.market_data.infrastructure.providers.yahoo_finance_provider import (
    YahooFinanceProvider,
)

# Module-level singleton state. These are intentionally created at most
# once per process and reused across every request, rather than per
# request, so the underlying HTTP connection pool is actually reused (per
# the sprint's "connection reuse" and "no duplicated requests"
# requirements) and so the in-memory cache is shared rather than
# reconstructed empty on every call.
_http_client: httpx.AsyncClient | None = None
_cache: MarketDataCachePort | None = None
_provider: MarketDataProviderPort | None = None
_service: GetMarketIndicesSnapshotService | None = None

# Guards both initialization and shutdown of the singletons above, so
# startup/first-request construction can never race against a shutdown
# call, and concurrent requests before initialization completes can never
# each construct their own AsyncClient/provider/service.
_init_lock = asyncio.Lock()


async def _get_or_create_service() -> GetMarketIndicesSnapshotService:
    """
    Returns the process-wide GetMarketIndicesSnapshotService singleton,
    constructing it (and its dependencies) on first call.

    Uses double-checked locking: the fast path (already initialized) never
    acquires the lock, and the lock is only taken for the one-time
    construction, so steady-state request handling incurs no lock
    contention. In normal operation this construction happens once, during
    market_data_lifespan()'s startup phase, rather than lazily on the
    first request -- the lazy path remains as a safety net for any caller
    that resolves the dependency outside the lifespan-managed app.

    Settings are resolved via get_settings() (itself a singleton getter,
    so this does not re-parse environment variables on every call) once,
    inside the lock, at construction time.
    """
    global _http_client, _cache, _provider, _service

    if _service is not None:
        return _service

    async with _init_lock:
        if _service is not None:
            return _service

        settings = get_settings()

        _http_client = httpx.AsyncClient()
        _cache = InMemoryMarketDataCache()
        _provider = YahooFinanceProvider(
            http_client=_http_client,
            request_timeout_seconds=settings.market_data_request_timeout_seconds,
        )
        _service = GetMarketIndicesSnapshotService(
            provider=_provider,
            cache=_cache,
            cache_ttl_seconds=settings.market_data_cache_ttl_seconds,
        )
        return _service


async def get_market_indices_snapshot_service() -> GetMarketIndicesSnapshotService:
    """
    FastAPI dependency that resolves to the shared
    GetMarketIndicesSnapshotService instance.

    Route handlers (api/routes.py) declare this as a dependency to obtain
    the service without knowing anything about how it, or the provider and
    cache behind it, were constructed.
    """
    return await _get_or_create_service()


async def close_market_data_dependencies() -> None:
    """
    Releases resources held by this module's singleton dependencies --
    specifically, closes the shared httpx.AsyncClient's connection pool.

    Idempotent and safe to call multiple times: the module-level
    references are captured locally and cleared while holding
    `_init_lock` (so a concurrent initialization or a second, overlapping
    shutdown call cannot observe or act on a half-torn-down state), and
    the actual client close happens afterward, outside the lock, using
    only the locally captured reference. If the client was never
    constructed, or a prior call already closed and cleared it, this
    method does nothing.

    Any error raised by AsyncClient.aclose() is intentionally not caught
    here -- application shutdown should be able to observe and report a
    cleanup failure rather than have it silently suppressed.
    """
    global _http_client, _cache, _provider, _service

    async with _init_lock:
        client_to_close = _http_client
        _http_client = None
        _cache = None
        _provider = None
        _service = None

    if client_to_close is not None:
        await client_to_close.aclose()


@asynccontextmanager
async def market_data_lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    FastAPI lifespan context manager for the market_data module.

    Wired into the application's composed lifespan in backend/app/main.py
    so that:
      - this module's shared AsyncClient/cache/provider/service are
        constructed once during application startup, rather than lazily
        on the first request; and
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
        await close_market_data_dependencies()