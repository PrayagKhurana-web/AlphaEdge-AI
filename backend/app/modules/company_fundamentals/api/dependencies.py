"""FastAPI dependency wiring for the company_fundamentals module.

Unlike a simple per-request construction pattern, this module owns its
own private, process-wide singletons: a dedicated ``httpx.AsyncClient``,
a ``FundamentalsProviderPort`` implementation, and the
``CompanyFundamentalsService`` built on top of it. This mirrors the
stock_details module's singleton-plus-lifespan pattern rather than
sharing another module's HTTP client, so each module owns and controls
the lifetime of its own outbound connections.

Object lifetime:
- ``company_fundamentals_lifespan`` eagerly creates the singleton
  ``AsyncClient``/provider/service at application startup and closes
  them at shutdown.
- ``_get_or_create_service`` additionally supports lazy, double-checked
  locked initialization for any caller that runs before the lifespan has
  completed startup (e.g. in tests that construct the dependency
  directly), so the module remains safe to use even without the
  lifespan wired in.
- No business logic, request validation, response mapping, or HTTP
  exception translation lives in this file — routes depend only on the
  application service dependency alias below.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

import httpx
from fastapi import Depends, FastAPI

from app.core.config import get_settings
from ..application.ports import FundamentalsProviderPort
from ..application.services import CompanyFundamentalsService
from ..infrastructure.providers.yahoo_fundamentals_provider import (
    YahooFundamentalsProvider,
)

_http_client: httpx.AsyncClient | None = None
_provider: FundamentalsProviderPort | None = None
_service: CompanyFundamentalsService | None = None
_initialization_lock = asyncio.Lock()


async def _get_or_create_service() -> CompanyFundamentalsService:
    """Return the process-wide company fundamentals service singleton.

    Uses double-checked locking: the fast path returns the already-built
    singleton with no lock contention, and only the first caller that
    finds it unbuilt pays the cost of acquiring ``_initialization_lock``
    and constructing it. Settings are resolved only during this initial
    construction, not on every call.
    """
    global _http_client, _provider, _service

    if _service is not None:
        return _service

    async with _initialization_lock:
        if _service is not None:
            return _service

        settings = get_settings()

        _http_client = httpx.AsyncClient()
        _provider = YahooFundamentalsProvider(
            http_client=_http_client,
            request_timeout_seconds=settings.company_fundamentals_request_timeout_seconds,
        )
        _service = CompanyFundamentalsService(provider=_provider)

        return _service


async def get_company_fundamentals_service() -> CompanyFundamentalsService:
    """FastAPI dependency returning the company fundamentals service.

    Delegates entirely to ``_get_or_create_service``; this function
    exists as the stable dependency-injection entry point that routes
    depend on.
    """
    return await _get_or_create_service()


CompanyFundamentalsServiceDependency = Annotated[
    CompanyFundamentalsService,
    Depends(get_company_fundamentals_service),
]


async def close_company_fundamentals_dependencies() -> None:
    """Close the module's singleton AsyncClient and reset all state.

    Idempotent: calling this when nothing has been initialized, or
    calling it more than once, is a no-op beyond the first successful
    close. The client is captured under the lock and closed outside of
    it, so a slow ``aclose()`` never blocks other callers waiting on
    ``_initialization_lock``. Failures from ``aclose()`` are not
    suppressed.
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
async def company_fundamentals_lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan for the company_fundamentals module.

    Eagerly initializes the module's singleton AsyncClient, provider,
    and service before yielding control, and closes them in a ``finally``
    block on shutdown so cleanup runs even if startup after this point
    fails or the application is interrupted.
    """
    await _get_or_create_service()
    try:
        yield
    finally:
        await close_company_fundamentals_dependencies()