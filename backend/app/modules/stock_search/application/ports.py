"""
Application-layer port (abstract interface) for the stock_search module.

A "port" here is a contract the application layer depends on but does not
implement -- concrete implementations live in infrastructure/ and are
wired in via dependency injection. This is what lets the search backend
(Postgres full-text search, pg_trgm, or an external search service, all
undecided as of this sprint) change without any change to
application/services.py or the API routes that depend on it.

An ABC is used here (rather than a typing.Protocol) for consistency with
market_data/application/ports.py's MarketDataProviderPort/
MarketDataCachePort, and because an ABC gives a concrete base class that
test doubles can subclass explicitly, making the contract being satisfied
unambiguous at the point a fake is defined.

Per PROJECT_CONTEXT.md's Clean Architecture rule, this file may import
from domain/ (entities, exceptions) but must never import FastAPI,
Pydantic, an HTTP client library, a database driver, or any other
infrastructure-layer concern.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.modules.stock_search.domain.entities import StockSearchResults
from app.modules.stock_search.domain.exceptions import (  # noqa: F401 -- referenced in docstrings
    InvalidSearchResultError,
    SearchProviderRateLimitedError,
    SearchProviderTimeoutError,
    SearchProviderUnavailableError,
)


class StockSearchProviderPort(ABC):
    """
    Abstract contract for any backend capable of searching for stocks by a
    free-text query.

    Concrete implementations are responsible for translating their own
    backend's responses and errors into this module's domain exceptions
    (SearchProviderTimeoutError, SearchProviderRateLimitedError,
    SearchProviderUnavailableError, InvalidSearchResultError) -- callers of
    this port should never need to catch a backend-specific exception
    type.
    """

    @abstractmethod
    async def search(
        self,
        query: str,
        *,
        limit: int,
    ) -> StockSearchResults:
        """
        Searches for stocks matching `query` and returns up to `limit`
        results in relevance order.

        Args:
            query: The search text. Callers of this port (the application
                layer) are responsible for normalizing and validating the
                query -- e.g. stripping whitespace, rejecting empty or
                overlong queries -- before calling this method, per the
                domain exceptions defined for that purpose
                (EmptySearchQueryError, SearchQueryTooLongError,
                InvalidSearchQueryError). Implementations are not required
                to re-validate `query` against those rules.
            limit: The maximum number of results to return. Must be
                strictly positive; implementations may assume this has
                already been validated by the caller.

        Returns:
            A StockSearchResults containing up to `limit` matches, ordered
            by relevance (most relevant first). May contain fewer than
            `limit` results if fewer matches exist. A query that is valid
            but matches nothing returns a StockSearchResults with zero
            items -- this is a normal, successful outcome, not a failure
            state, and must not raise.

        Raises:
            SearchProviderTimeoutError: if the backend did not respond in
                time.
            SearchProviderRateLimitedError: if the backend reports its
                rate limit has been exceeded.
            SearchProviderUnavailableError: if the backend could not be
                reached or reported an outage.
            InvalidSearchResultError: if the backend responded but its
                data could not be interpreted as valid
                StockSearchResult entries.
        """
        raise NotImplementedError