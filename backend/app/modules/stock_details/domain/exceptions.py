"""
Domain-level exceptions for the stock_details module.

These represent failure conditions as domain concepts (a malformed
display symbol, an upstream quote provider being unreachable, unusable
quote data) rather than as HTTP status codes or provider-specific error
types. Per PROJECT_CONTEXT.md's Clean Architecture rule, this file must
never import FastAPI, HTTP status codes, httpx, or any infrastructure-
layer concern (a specific quote provider's client errors, etc.) --
infrastructure adapters catch their own provider-specific exceptions and
re-raise as one of these, so application/services.py (and everything
above it) only ever needs to know this module's own exception hierarchy,
never which concrete provider is in use.
"""

from __future__ import annotations


class StockDetailsError(Exception):
    """
    Base class for every domain-level error this module can raise.

    Application and API code that wants to handle "any stock details
    failure" generically can catch this; code that needs to distinguish
    specific failure modes should catch the relevant subclass instead.
    """


class InvalidDisplaySymbolError(StockDetailsError):
    """
    Raised when the supplied display symbol is empty or malformed.

    This is raised by the application layer (application/services.py)
    before any provider is ever consulted -- it represents a caller-input
    problem (an unparseable or empty display symbol), not a provider
    failure, and is distinct from QuoteProviderError and its subclasses
    below.

    Attributes:
        display_symbol: The offending display symbol, included for
            diagnostics. Not guaranteed to be safe to display verbatim to
            an end user in every context; callers presenting this to a
            user should still apply their own display-layer escaping/
            formatting.
        reason: A normalized (stripped), non-empty explanation of why the
            display symbol was rejected.

    Raises (at construction):
        ValueError: if `reason` is empty or whitespace-only after
            stripping.
    """

    def __init__(self, display_symbol: str, *, reason: str) -> None:
        normalized_reason = reason.strip()
        if not normalized_reason:
            raise ValueError("reason must be a non-empty string after stripping.")

        self.display_symbol = display_symbol
        self.reason = normalized_reason
        super().__init__(f"Invalid display symbol {display_symbol!r}: {normalized_reason}")


class QuoteProviderError(StockDetailsError):
    """
    Base class for failures originating from an upstream quote provider
    (whichever concrete backend -- Yahoo Finance or a future replacement
    -- ultimately answers the request). Infrastructure adapters catch
    their own provider-specific exceptions (an HTTP client's timeout
    error, a parsing error, etc.) and re-raise as one of this class's
    subclasses, so the application layer never needs to know which
    concrete provider is in use. application/services.py should never see
    a provider-specific exception type (e.g. an httpx exception) directly
    -- if it ever does, that indicates a missing translation in the
    infrastructure adapter, which is a bug in that adapter, not a
    condition application/services.py should be expected to handle.

    Attributes:
        provider_name: A normalized (stripped), non-empty identifier for
            the provider that raised this error.

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


class QuoteProviderTimeoutError(QuoteProviderError):
    """
    Raised when a request to the upstream quote provider did not complete
    in time.

    Raised exclusively by infrastructure-layer provider adapters, in
    response to their own transport-level timeout (e.g. an httpx
    TimeoutException) -- never raised directly by application/services.py.
    """


class QuoteProviderUnavailableError(QuoteProviderError):
    """
    Raised when the upstream quote provider could not be reached at all,
    or responded with a failure indicating it is currently down or
    refusing requests (distinct from a rate limit, which is a specific,
    recoverable case of unavailability -- see
    QuoteProviderRateLimitedError).

    Raised exclusively by infrastructure-layer provider adapters, in
    response to their own connection/transport failures or a provider
    outage/access-denial status -- never raised directly by
    application/services.py.
    """


class QuoteProviderRateLimitedError(QuoteProviderError):
    """
    Raised when the upstream quote provider indicates its rate limit has
    been exceeded. Kept distinct from QuoteProviderUnavailableError
    because callers (e.g. a retry policy) may want to back off
    differently for a rate limit than for a general outage.

    Raised exclusively by infrastructure-layer provider adapters, upon
    observing a provider-specific rate-limit signal (e.g. an HTTP 429) --
    never raised directly by application/services.py.

    Attributes:
        retry_after_seconds: The provider's suggested wait time before
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


class InvalidQuoteDataError(QuoteProviderError):
    """
    Raised when the upstream quote provider responded successfully (no
    timeout, no rate limit, no outage) but the payload could not be
    converted into a valid StockQuote -- e.g. a missing price field, a
    non-numeric value where a number was expected, an unusable timestamp,
    or a response shape that doesn't match what the infrastructure
    adapter expects.

    Raised exclusively by infrastructure-layer provider adapters, at the
    point where raw provider data fails to parse into the domain's
    StockQuote entity (whether because a required field is missing, or
    because StockQuote's own validation rejects the assembled values) --
    never raised directly by application/services.py.

    Attributes:
        display_symbol: The display symbol the unusable data was
            associated with, if known. None if the failure occurred
            before a display symbol could be determined.
    """

    def __init__(
        self,
        message: str,
        *,
        provider_name: str,
        display_symbol: str | None = None,
    ) -> None:
        self.display_symbol = display_symbol
        super().__init__(message, provider_name=provider_name)