"""
Application-layer use case for searching stocks by a free-text query.

This module contains the orchestration logic that validates and
normalizes a caller-supplied query, resolves a result limit, and delegates
to the injected StockSearchProviderPort -- per PROJECT_CONTEXT.md's Clean
Architecture rule, it depends only on application/ports.py and
domain/entities.py + domain/exceptions.py, never on FastAPI, Pydantic, an
HTTP client, a database driver, or any concrete provider implementation.
"""

from __future__ import annotations

import re

from app.modules.stock_search.application.ports import StockSearchProviderPort
from app.modules.stock_search.domain.entities import StockSearchResults
from app.modules.stock_search.domain.exceptions import (
    EmptySearchQueryError,
    InvalidSearchQueryError,
    SearchQueryTooLongError,
)

# Characters this module accepts in a search query: letters (any case),
# digits, spaces, dots, hyphens, ampersands, and parentheses -- enough to
# cover symbols ("M&M"), company names with punctuation ("Dr. Reddy's"
# would still need an apostrophe, deliberately not included here since it
# was not in the requested character set), and parenthesized suffixes
# ("Tata Motors (DVR)"). Any character outside this set is rejected
# outright rather than silently stripped.
_ALLOWED_QUERY_PATTERN = re.compile(r"^[A-Za-z0-9 .\-&()]+$")


class SearchStocksService:
    """
    Use case: validate and normalize a free-text search query, resolve a
    result limit, and return matching stocks via the injected
    StockSearchProviderPort.

    This service is the only place in the module that decides what counts
    as a valid query and what the effective result limit should be -- the
    provider implementation is only ever asked to search with an
    already-validated query and a resolved, positive limit.
    """

    def __init__(
        self,
        provider: StockSearchProviderPort,
        max_query_length: int,
        default_limit: int,
        max_limit: int,
    ) -> None:
        """
        Args:
            provider: Search backend, satisfying StockSearchProviderPort.
            max_query_length: Maximum accepted length of a normalized
                query. Must be strictly positive.
            default_limit: Result limit used when the caller does not
                specify one. Must be strictly positive and must not
                exceed `max_limit`.
            max_limit: Maximum result limit a caller may request. Must be
                strictly positive.

        Raises:
            ValueError: if `max_query_length`, `default_limit`, or
                `max_limit` is not strictly positive, or if
                `default_limit` exceeds `max_limit`.
        """
        if max_query_length <= 0:
            raise ValueError(
                f"max_query_length must be strictly positive, got {max_query_length!r}"
            )
        if default_limit <= 0:
            raise ValueError(
                f"default_limit must be strictly positive, got {default_limit!r}"
            )
        if max_limit <= 0:
            raise ValueError(
                f"max_limit must be strictly positive, got {max_limit!r}"
            )
        if default_limit > max_limit:
            raise ValueError(
                f"default_limit ({default_limit}) must not exceed "
                f"max_limit ({max_limit})"
            )

        self._provider = provider
        self._max_query_length = max_query_length
        self._default_limit = default_limit
        self._max_limit = max_limit

    async def search(
        self,
        query: str,
        *,
        limit: int | None = None,
    ) -> StockSearchResults:
        """
        Validates `query` and `limit`, then delegates to the provider.

        Args:
            query: Raw, caller-supplied search text.
            limit: Maximum number of results to return. If None,
                `default_limit` is used.

        Returns:
            A StockSearchResults containing up to the resolved limit of
            matches, in the order returned by the provider. An empty
            result is valid and is returned as-is, not raised.

        Raises:
            EmptySearchQueryError: if `query` is empty or whitespace-only
                after normalization.
            SearchQueryTooLongError: if the normalized query exceeds
                `max_query_length`.
            InvalidSearchQueryError: if the normalized query contains
                characters outside this module's supported set.
            ValueError: if `limit` is provided and is less than or equal
                to zero, or exceeds `max_limit`.
            SearchProviderTimeoutError, SearchProviderRateLimitedError,
            SearchProviderUnavailableError, InvalidSearchResultError:
                propagated unchanged from the provider.
        """
        normalized_query = self._normalize_and_validate_query(query)
        resolved_limit = self._resolve_limit(limit)

        results = await self._provider.search(normalized_query, limit=resolved_limit)

        return self._truncate_if_needed(results, resolved_limit)

    def _normalize_and_validate_query(self, query: str) -> str:
        """
        Strips leading/trailing whitespace and validates the result
        against this module's length and character rules.

        Case is preserved exactly as supplied (normalization here is
        limited to whitespace trimming, not case-folding) -- case-folding,
        if ever needed for matching purposes, is a provider-level
        concern, not a query-shape validation rule.

        Raises:
            EmptySearchQueryError: if the stripped query is empty.
            SearchQueryTooLongError: if the stripped query exceeds
                `max_query_length`.
            InvalidSearchQueryError: if the stripped query contains a
                character outside the allowed set. Invalid characters are
                never silently removed -- an invalid query is rejected,
                not repaired.
        """
        normalized_query = query.strip()

        if not normalized_query:
            raise EmptySearchQueryError()

        if len(normalized_query) > self._max_query_length:
            raise SearchQueryTooLongError(
                query_length=len(normalized_query),
                max_length=self._max_query_length,
            )

        if not _ALLOWED_QUERY_PATTERN.match(normalized_query):
            raise InvalidSearchQueryError(
                normalized_query,
                reason=(
                    "query contains unsupported characters; only letters, "
                    "numbers, spaces, dots, hyphens, ampersands, and "
                    "parentheses are allowed"
                ),
            )

        return normalized_query

    def _resolve_limit(self, limit: int | None) -> int:
        """
        Resolves the effective result limit: `default_limit` if `limit`
        is None, otherwise `limit` itself after validation.

        Raises:
            ValueError: if `limit` is provided and is less than or equal
                to zero, or exceeds `max_limit`.
        """
        if limit is None:
            return self._default_limit

        if limit <= 0:
            raise ValueError(f"limit must be strictly positive, got {limit!r}")
        if limit > self._max_limit:
            raise ValueError(
                f"limit ({limit}) must not exceed max_limit ({self._max_limit})"
            )

        return limit

    def _truncate_if_needed(
        self, results: StockSearchResults, limit: int
    ) -> StockSearchResults:
        """
        Defensively truncates `results` to at most `limit` entries,
        preserving order, in case the provider returned more than was
        requested. Returns `results` unchanged (no new object constructed)
        when it is already within the limit, since StockSearchResults is
        immutable and there is nothing to correct.
        """
        if len(results) <= limit:
            return results

        return StockSearchResults(results=results.results[:limit])