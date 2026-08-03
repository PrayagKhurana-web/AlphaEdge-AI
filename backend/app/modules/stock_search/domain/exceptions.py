"""
Domain-level exceptions for the stock_search module.

These represent failure conditions as domain concepts (an invalid query,
an upstream search backend being unreachable, unusable result data) rather
than as HTTP status codes or backend-specific error types. Per
PROJECT_CONTEXT.md's Clean Architecture rule, this file must never import
FastAPI, HTTP status codes, or any infrastructure-layer concern (a
specific search backend's client errors, etc.) -- infrastructure adapters
catch their own backend-specific exceptions and re-raise as one of these.
"""

from __future__ import annotations


class StockSearchError(Exception):
    """
    Base class for every domain-level error this module can raise.

    Application and API code that wants to handle "any stock search
    failure" generically can catch this; code that needs to distinguish
    specific failure modes should catch the relevant subclass instead.
    """


class EmptySearchQueryError(StockSearchError):
    """
    Raised when the caller attempts to search using an empty or
    whitespace-only query.

    This is a domain concept, not a backend concept: it means "there is
    nothing here worth searching for," independent of whichever search
    backend would otherwise have been asked to run the query.
    """

    def __init__(self) -> None:
        super().__init__("Search query must not be empty or whitespace-only.")


class SearchQueryTooLongError(StockSearchError):
    """
    Raised when the query exceeds the module's supported maximum length.

    Attributes:
        query_length: The length of the offending query.
        max_length: The maximum length this module supports.

    Raises (at construction):
        ValueError: if `query_length` is negative, if `max_length` is
            less than or equal to zero, or if `query_length` does not
            actually exceed `max_length` -- this exception represents
            only the case of a query that genuinely exceeds the maximum,
            not an arbitrary length pairing.
    """

    def __init__(self, query_length: int, max_length: int) -> None:
        if query_length < 0:
            raise ValueError(
                f"query_length must be non-negative, got {query_length!r}"
            )
        if max_length <= 0:
            raise ValueError(
                f"max_length must be strictly positive, got {max_length!r}"
            )
        if query_length <= max_length:
            raise ValueError(
                f"query_length ({query_length}) must exceed max_length "
                f"({max_length}) -- this exception represents only a "
                "query that actually exceeds the maximum."
            )

        self.query_length = query_length
        self.max_length = max_length
        super().__init__(
            f"Search query is too long ({query_length} characters); "
            f"the maximum supported length is {max_length} characters."
        )


class InvalidSearchQueryError(StockSearchError):
    """
    Raised when the query contains unsupported or invalid characters
    according to the domain's search rules.

    Attributes:
        query: The offending query, included for diagnostics. Not
            guaranteed to be safe to display verbatim to an end user in
            every context; callers presenting this to a user should still
            apply their own display-layer escaping/formatting.
        reason: A normalized (stripped), non-empty explanation of why the
            query was rejected.

    Raises (at construction):
        ValueError: if `reason` is empty or whitespace-only after
            stripping.
    """

    def __init__(self, query: str, *, reason: str) -> None:
        normalized_reason = reason.strip()
        if not normalized_reason:
            raise ValueError("reason must be a non-empty string after stripping.")

        self.query = query
        self.reason = normalized_reason
        super().__init__(f"Search query is invalid: {normalized_reason}")


class SearchProviderError(StockSearchError):
    """
    Base class for failures originating from an upstream search backend
    (whichever concrete mechanism -- Postgres full-text search, pg_trgm,
    an external search service -- ultimately answers the query).
    Infrastructure adapters catch their own backend-specific exceptions
    (a database driver's error, an HTTP client's timeout error, a parsing
    error, etc.) and re-raise as one of this class's subclasses, so the
    application layer never needs to know which concrete backend is in
    use.

    Attributes:
        provider_name: A normalized (stripped), non-empty identifier for
            the backend that raised this error.

    Raises (at construction):
        ValueError: if `provider_name` is empty or whitespace-only after
            stripping.
    """

    def __init__(self, message: str, *, provider_name: str) -> None:
        normalized_provider_name = provider_name.strip()
        if not normalized_provider_name:
            raise ValueError("provider_name must be a non-empty string after stripping.")

        self.provider_name = normalized_provider_name
        super().__init__(f"[{normalized_provider_name}] {message}")


class SearchProviderTimeoutError(SearchProviderError):
    """Raised when a request to the upstream search backend did not complete in time."""


class SearchProviderUnavailableError(SearchProviderError):
    """
    Raised when the upstream search backend could not be reached at all,
    or responded with a failure indicating it is currently down or
    refusing requests (distinct from a rate limit, which is a specific,
    recoverable case of unavailability -- see
    SearchProviderRateLimitedError).
    """


class SearchProviderRateLimitedError(SearchProviderError):
    """
    Raised when the upstream search backend indicates its rate limit has
    been exceeded. Kept distinct from SearchProviderUnavailableError
    because callers (e.g. a retry policy) may want to back off
    differently for a rate limit than for a general outage.

    Attributes:
        retry_after_seconds: The backend's suggested wait time before
            retrying, if it supplied one. None if unknown.

    Raises (at construction):
        ValueError: if `retry_after_seconds` is provided and is negative.
            None remains a valid value, meaning "unknown."
    """

    def __init__(
        self,
        message: str,
        *,
        provider_name: str,
        retry_after_seconds: int | None = None,
    ) -> None:
        if retry_after_seconds is not None and retry_after_seconds < 0:
            raise ValueError(
                "retry_after_seconds must be non-negative or None, got "
                f"{retry_after_seconds!r}"
            )

        self.retry_after_seconds = retry_after_seconds
        super().__init__(message, provider_name=provider_name)


class InvalidSearchResultError(SearchProviderError):
    """
    Raised when the upstream search backend responded successfully (no
    timeout, no rate limit, no outage) but the payload could not be
    interpreted as valid StockSearchResult entities -- e.g. a missing
    symbol field, an unrecognized exchange value, or a response shape that
    doesn't match what the infrastructure adapter expects.
    """

    def __init__(
        self,
        message: str,
        *,
        provider_name: str,
        query: str | None = None,
    ) -> None:
        self.query = query
        super().__init__(message, provider_name=provider_name)