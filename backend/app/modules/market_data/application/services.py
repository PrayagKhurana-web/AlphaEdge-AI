"""
Application-layer use case for retrieving live market index quotes.

This module contains the orchestration logic that ties the provider port
and the cache port together (per File 3's interfaces) into the single
capability the API layer needs: "give me the current snapshot of all
tracked indices." It depends only on the abstractions defined in
application/ports.py and the entities/exceptions defined in domain/ --
never on FastAPI, Redis, an HTTP client, Pydantic, or any configuration
module, per PROJECT_CONTEXT.md's Clean Architecture rule.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.modules.market_data.application.ports import (
    MarketDataCachePort,
    MarketDataProviderPort,
)
from app.modules.market_data.domain.entities import (
    IndexSymbol,
    MarketIndicesSnapshot,
)
from app.modules.market_data.domain.exceptions import InvalidQuoteDataError

logger = logging.getLogger(__name__)


class GetMarketIndicesSnapshotService:
    """
    Use case: return the current MarketIndicesSnapshot for every index this
    module tracks, preferring a cached snapshot when one is available and
    falling back to the upstream provider on a cache miss.

    This service is the only place in the module that decides *when* to
    consult the cache versus the provider -- the provider and cache
    implementations themselves have no awareness of each other.
    """

    def __init__(
        self,
        provider: MarketDataProviderPort,
        cache: MarketDataCachePort,
        cache_ttl_seconds: int,
    ) -> None:
        """
        Args:
            provider: Source of live quotes, satisfying MarketDataProviderPort.
            cache: Snapshot cache, satisfying MarketDataCachePort.
            cache_ttl_seconds: How long a freshly fetched snapshot should
                remain cached. Must be strictly positive.

        Raises:
            ValueError: if `cache_ttl_seconds` is less than or equal to
                zero.
        """
        if cache_ttl_seconds <= 0:
            raise ValueError(
                f"cache_ttl_seconds must be strictly positive, got "
                f"{cache_ttl_seconds!r}"
            )
        self._provider = provider
        self._cache = cache
        self._cache_ttl_seconds = cache_ttl_seconds

    async def get_market_indices_snapshot(self) -> MarketIndicesSnapshot:
        """
        Returns the current MarketIndicesSnapshot, from cache if available
        and unexpired, otherwise freshly fetched from the provider and
        cached for subsequent callers.

        Returns:
            A MarketIndicesSnapshot containing whichever tracked indices
            were available (from cache, or from a fresh provider fetch).

        Raises:
            SymbolNotFoundError: propagated from the provider if it does
                not recognize one of this module's tracked symbols --
                this indicates a configuration mismatch and must not be
                hidden.
            ProviderTimeoutError: propagated from the provider on a fresh
                fetch.
            ProviderRateLimitedError: propagated from the provider on a
                fresh fetch.
            ProviderUnavailableError: propagated from the provider on a
                fresh fetch.
            InvalidQuoteDataError: propagated from the provider on a fresh
                fetch, or raised directly by this service if the provider
                returns zero quotes for a non-empty request without
                raising an exception itself.
        """
        cached_snapshot = await self._try_get_cached_snapshot()
        if cached_snapshot is not None:
            return cached_snapshot

        fresh_snapshot = await self._fetch_fresh_snapshot()
        await self._try_cache_snapshot(fresh_snapshot)
        return fresh_snapshot

    async def _try_get_cached_snapshot(self) -> MarketIndicesSnapshot | None:
        """
        Attempts to read the current snapshot from the cache.

        Cache reads are treated as best-effort: if the cache backend
        raises anything at all (a connection error, a deserialization
        error, or any other runtime failure within the cache
        implementation), that failure is logged and swallowed here so the
        caller falls through to the provider instead of failing the whole
        request over a cache problem. This intentionally catches the broad
        `Exception` base (never `BaseException`, so `KeyboardInterrupt`
        and `SystemExit` are never suppressed) because a cache-layer
        implementation is not expected to raise this module's own domain
        exceptions, and coupling this method to a specific infrastructure
        exception type would violate the Clean Architecture boundary this
        module depends on MarketDataCachePort to maintain.

        A cached snapshot containing zero quotes is treated as equivalent
        to a cache miss (logged as a warning, then None is returned) --
        an empty snapshot is not a usable result, and the caller should
        fall through to the provider exactly as it would on a true miss.

        Returns:
            The cached snapshot if one was present, readable, and
            contained at least one quote; otherwise None.
        """
        try:
            cached_snapshot = await self._cache.get_market_indices_snapshot()
        except Exception:
            logger.warning(
                "market_data cache read failed; falling back to provider",
                exc_info=True,
            )
            return None

        if cached_snapshot is None:
            return None

        if not cached_snapshot.quotes:
            logger.warning(
                "market_data cache returned an empty snapshot; "
                "treating as a cache miss and falling back to provider"
            )
            return None

        return cached_snapshot

    async def _fetch_fresh_snapshot(self) -> MarketIndicesSnapshot:
        """
        Fetches quotes for every tracked index in a single provider call
        and assembles them into a new snapshot.

        Domain exceptions raised by the provider (SymbolNotFoundError,
        ProviderTimeoutError, ProviderRateLimitedError,
        ProviderUnavailableError, InvalidQuoteDataError) are never caught
        here -- they are genuine failures the caller must see. The one
        case this method adds validation for is a provider call that
        *succeeds* (raises nothing) but returns zero quotes for a
        non-empty request, which the provider port's contract permits as
        a form of partial-failure signaling; this service treats that
        specific outcome as equivalent to InvalidQuoteDataError, since a
        snapshot with no data in it is not a usable result.
        """
        tracked_symbols = list(IndexSymbol)
        quotes = await self._provider.get_quotes(tracked_symbols)

        if not quotes:
            raise InvalidQuoteDataError(
                "Provider returned zero quotes for a non-empty request "
                f"of {len(tracked_symbols)} tracked symbol(s).",
                provider_name=type(self._provider).__name__,
            )

        return MarketIndicesSnapshot(
            quotes=quotes,
            generated_at=datetime.now(timezone.utc),
        )

    async def _try_cache_snapshot(self, snapshot: MarketIndicesSnapshot) -> None:
        """
        Attempts to store a freshly fetched snapshot in the cache.

        Cache writes, like cache reads, are best-effort: a fresh snapshot
        was already successfully fetched from the provider, so a caching
        failure must not prevent that snapshot from being returned to the
        caller. Any exception raised by the cache implementation is logged
        and swallowed here for the same reason and with the same
        `Exception`-not-`BaseException` scope as `_try_get_cached_snapshot`.
        """
        try:
            await self._cache.set_market_indices_snapshot(
                snapshot, ttl_seconds=self._cache_ttl_seconds
            )
        except Exception:
            logger.warning(
                "market_data cache write failed; returning uncached snapshot",
                exc_info=True,
            )