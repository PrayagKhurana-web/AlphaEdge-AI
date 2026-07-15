"""
Application-layer ports (abstract interfaces) for the market_data module's
live index tracking capability.

A "port" here is a contract the application layer depends on but does not
implement -- concrete implementations live in infrastructure/ and are wired
in via dependency injection (api/dependencies.py, File 8). This is what
lets the provider (Yahoo Finance today, possibly NSE/BSE/Polygon/
AlphaVantage/TwelveData tomorrow) and the cache backend (Redis in
production, in-memory for local dev) change without any change to
application/services.py or the API routes that depend on it.

Per PROJECT_CONTEXT.md's Clean Architecture rule, this file may import from
domain/ (entities, exceptions) but must never import FastAPI, an HTTP
client library, Redis, JSON serialization concerns, or any other
infrastructure-layer concern.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence

from app.modules.market_data.domain.entities import (
    IndexQuote,
    IndexSymbol,
    MarketIndicesSnapshot,
)


class MarketDataProviderPort(ABC):
    """
    Abstract contract for any upstream source of live index quotes.

    Concrete implementations (infrastructure/providers/yahoo_finance_provider.py
    today) are responsible for translating their own client library's
    responses and errors into this module's domain entities and domain
    exceptions (SymbolNotFoundError, ProviderTimeoutError,
    ProviderUnavailableError, ProviderRateLimitedError,
    InvalidQuoteDataError) -- callers of this port should never need to
    catch a provider-specific exception type.
    """

    @abstractmethod
    async def get_quote(self, symbol: IndexSymbol) -> IndexQuote:
        """
        Fetches a single index's current quote from the upstream provider.

        Args:
            symbol: The canonical index to fetch.

        Returns:
            The current IndexQuote for that symbol.

        Raises:
            SymbolNotFoundError: if this provider has no mapping for the
                requested symbol.
            ProviderTimeoutError: if the upstream request did not complete
                in time.
            ProviderRateLimitedError: if the provider reports its rate
                limit has been exceeded.
            ProviderUnavailableError: if the provider could not be reached
                or reported an outage.
            InvalidQuoteDataError: if the provider responded but the
                payload could not be interpreted as a valid quote.
        """
        raise NotImplementedError

    @abstractmethod
    async def get_quotes(
        self, symbols: Sequence[IndexSymbol]
    ) -> Mapping[IndexSymbol, IndexQuote]:
        """
        Fetches quotes for multiple indices, ideally in a single batched
        upstream call where the provider supports it (implementations
        should prefer this over calling get_quote() in a loop, to avoid
        the "no duplicated requests" requirement being violated at the
        provider layer).

        Failure handling, precisely:
          - If `symbols` contains a symbol this provider has no mapping
            for, raise SymbolNotFoundError for that symbol -- an unknown
            symbol is a caller error, not a partial-data situation, and
            must not be silently dropped from the result.
          - If a *supported* symbol's quote is temporarily unavailable
            (e.g. the provider's response omitted it, or that single
            symbol's data could not be parsed) while other requested
            symbols succeeded, that symbol may simply be absent from the
            returned mapping rather than raising -- callers should treat
            a missing key as "unavailable right now," not as an error
            requiring the whole call to fail.
          - If the underlying request fails at the transport/provider
            level for all requested symbols (timeout, outage, or rate
            limit), raise the corresponding ProviderError subclass
            (ProviderTimeoutError, ProviderUnavailableError,
            ProviderRateLimitedError) rather than returning an empty or
            partial mapping -- this distinguishes "the provider is down"
            from "the provider is up but some data is momentarily thin."
          - If the provider responds successfully at the transport level
            but the response data is invalid for every requested symbol
            (so no valid quote can be extracted for any of them), raise
            InvalidQuoteDataError rather than returning an empty mapping
            -- an empty mapping should only ever mean "zero symbols were
            requested," never "all of them failed to parse."

        Args:
            symbols: The canonical indices to fetch.

        Returns:
            A mapping from each successfully-fetched, supported symbol to
            its quote. May be a strict subset of `symbols` if some
            supported symbols' data was temporarily unavailable, per the
            rules above.

        Raises:
            SymbolNotFoundError: if any requested symbol is not one this
                provider recognizes.
            ProviderTimeoutError: if the upstream request did not complete
                in time.
            ProviderRateLimitedError: if the provider reports its rate
                limit has been exceeded.
            ProviderUnavailableError: if the provider could not be reached
                or reported an outage.
            InvalidQuoteDataError: if the provider responded but no valid
                quote could be extracted for any requested symbol.
        """
        raise NotImplementedError


class MarketDataCachePort(ABC):
    """
    Abstract contract for caching a market indices snapshot, expressed in
    domain terms rather than as a generic string key/value store.

    This is deliberately typed to this feature's one cached object
    (MarketIndicesSnapshot) rather than exposing a generic get/set-by-key
    interface: cache-key naming, serialization format (JSON or otherwise),
    and the encoding of Decimal and datetime values into that format are
    infrastructure concerns owned entirely by the concrete implementation
    (infrastructure/cache.py, File 5) -- application/services.py (File 4)
    must be able to depend on this port without knowing or caring how the
    snapshot is actually stored.
    """

    @abstractmethod
    async def get_market_indices_snapshot(self) -> MarketIndicesSnapshot | None:
        """
        Returns the currently cached snapshot, or None if no snapshot is
        cached or the cached entry has expired.
        """
        raise NotImplementedError

    @abstractmethod
    async def set_market_indices_snapshot(
        self,
        snapshot: MarketIndicesSnapshot,
        *,
        ttl_seconds: int,
    ) -> None:
        """
        Stores `snapshot` as the current cached snapshot, expiring after
        `ttl_seconds` seconds.

        Args:
            snapshot: The snapshot to cache.
            ttl_seconds: Number of seconds until this entry expires. Must
                be strictly positive.

        Raises:
            ValueError: if `ttl_seconds` is less than or equal to zero.
                Implementations must raise rather than silently treating a
                non-positive value as "do not cache" or as some other
                fallback behavior -- an invalid TTL is a programming error
                at the call site and must fail loudly.
        """
        raise NotImplementedError