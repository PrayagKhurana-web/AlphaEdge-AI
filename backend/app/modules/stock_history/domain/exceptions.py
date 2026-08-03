"""
Domain-level exceptions for the stock_history module.

These represent failure conditions as domain concepts (a malformed
history request, an upstream history provider being unreachable, unusable
candle data) rather than as HTTP status codes or provider-specific error
types. Per PROJECT_CONTEXT.md's Clean Architecture rule, this file must
never import FastAPI, Pydantic, httpx, requests, configuration, or any
application-, infrastructure-, or api-layer concern.

The application layer (application/services.py) raises
InvalidHistoryRequestError itself, before any provider is ever contacted,
when a caller-supplied request is rejected outright (an empty or
malformed display symbol, an unsupported interval, an unsupported
period). Infrastructure-layer provider adapters catch their own
provider-specific exceptions (an HTTP client's timeout error, a parsing
error, etc.) and re-raise as one of the HistoryProviderError subclasses
below, so application/services.py never sees a provider-specific
exception type directly -- if it ever does, that indicates a missing
translation in the infrastructure adapter, which is a bug in that
adapter, not a condition application/services.py should be expected to
handle. The API layer, in a later file, is responsible for translating
every exception in this hierarchy into an HTTP response; this file itself
knows nothing about HTTP.

Timeout, rate limiting, general unavailability, and invalid data are kept
as four distinct concepts (rather than one generic "provider failed"
exception) because each implies a different, useful response for a
caller: a timeout or a general outage might be worth a blind retry after
a delay; a rate limit specifically tells the caller how long to wait (via
`retry_after_seconds`) rather than retrying immediately; and invalid data
means the provider is reachable and responding but the payload itself
cannot be trusted -- retrying immediately with the same request would
likely reproduce the same bad data rather than resolve anything.
"""

from __future__ import annotations


class HistoricalDataError(Exception):
    """
    Base class for every domain-level error this module can raise.

    Application and API code that wants to handle "any historical data
    failure" generically can catch this; code that needs to distinguish
    specific failure modes should catch the relevant subclass instead.
    """


class InvalidHistoryRequestError(HistoricalDataError):
    """
    Raised when the application layer rejects a caller-supplied history
    request before any provider is ever contacted.

    Examples include an empty or malformed display symbol, an unsupported
    interval, or an unsupported period. This is raised exclusively by
    application/services.py -- it represents a caller-input problem, not a
    provider failure, and is distinct from HistoryProviderError and its
    subclasses below.

    Attributes:
        display_symbol: The offending display symbol, included for
            diagnostics. Not guaranteed to be safe to display verbatim to
            an end user in every context; callers presenting this to a
            user should still apply their own display-layer escaping/
            formatting.
        reason: A normalized (stripped), non-empty explanation of why the
            request was rejected.

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
        super().__init__(
            f"Invalid history request for {display_symbol!r}: {normalized_reason}"
        )


class HistoryProviderError(HistoricalDataError):
    """
    Base class for failures originating from an upstream historical data
    provider (whichever concrete backend -- Yahoo Finance or a future
    replacement -- ultimately answers the request). Infrastructure
    adapters catch their own provider-specific exceptions (an HTTP
    client's timeout error, a parsing error, etc.) and re-raise as one of
    this class's subclasses, so the application layer never needs to know
    which concrete provider is in use. application/services.py should
    never see a provider-specific exception type (e.g. an httpx
    exception) directly -- if it ever does, that indicates a missing
    translation in the infrastructure adapter, which is a bug in that
    adapter, not a condition application/services.py should be expected
    to handle.

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


class HistoryProviderTimeoutError(HistoryProviderError):
    """
    Raised when a request to the upstream historical data provider did not
    complete in time.

    Raised exclusively by infrastructure-layer provider adapters, in
    response to their own transport-level timeout (e.g. an httpx
    TimeoutException) -- never raised directly by application/services.py.
    """


class HistoryProviderUnavailableError(HistoryProviderError):
    """
    Raised when the upstream historical data provider could not be
    reached at all, or responded with a failure indicating it is
    currently down, refusing requests, or otherwise temporarily
    unavailable (distinct from a rate limit, which is a specific,
    recoverable case of unavailability -- see
    HistoryProviderRateLimitedError).

    Raised exclusively by infrastructure-layer provider adapters, in
    response to their own connection/transport failures or a provider
    outage/access-denial status -- never raised directly by
    application/services.py.
    """


class HistoryProviderRateLimitedError(HistoryProviderError):
    """
    Raised when the upstream historical data provider indicates its rate
    limit has been exceeded. Kept distinct from
    HistoryProviderUnavailableError because callers (e.g. a retry policy)
    may want to back off differently for a rate limit than for a general
    outage.

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


class InvalidHistoricalDataError(HistoryProviderError):
    """
    Raised when the upstream historical data provider responded
    successfully (no timeout, no rate limit, no outage) but the payload
    could not be converted into valid historical candle data -- e.g. a
    missing OHLC field, an invalid or unusable timestamp, an invalid
    volume value, duplicate candles, unordered candles, or a malformed
    response shape that doesn't match what the infrastructure adapter
    expects.

    Raised exclusively by infrastructure-layer provider adapters, at the
    point where raw provider data fails to parse into the domain's
    HistoricalCandle/HistoricalSeries entities (whether because a
    required field is missing, or because those entities' own validation
    rejects the assembled values) -- never raised directly by
    application/services.py.

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