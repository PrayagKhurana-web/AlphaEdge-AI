"""
Domain-level exceptions for the market_data module's live index tracking
capability.

These represent failure conditions as domain concepts (a symbol that
doesn't exist, an upstream data source being unreachable, a malformed
quote) rather than as HTTP status codes or provider-specific error types.
Per PROJECT_CONTEXT.md's Clean Architecture rule, this file must never
import FastAPI, HTTP status codes, or any infrastructure-layer concern
(Yahoo Finance client errors, Redis errors, etc.) -- infrastructure adapters
catch their own provider-specific exceptions and re-raise as one of these.
"""

from __future__ import annotations

from app.modules.market_data.domain.entities import IndexSymbol


class MarketDataError(Exception):
    """
    Base class for every domain-level error this module can raise.

    Application and API code that wants to handle any market-data failure
    generically can catch this class. Code that needs to distinguish a
    specific failure mode should catch the relevant subclass.
    """


class SymbolNotFoundError(MarketDataError):
    """
    Raised when a requested index symbol is not one this module tracks.

    This is a domain concept, not a provider concept. It means AlphaEdge AI
    has no definition for the requested symbol.
    """

    def __init__(self, symbol: IndexSymbol | str) -> None:
        self.symbol = symbol
        super().__init__(f"Unknown or untracked index symbol: {symbol!r}")


class ProviderError(MarketDataError):
    """
    Base class for failures originating from an upstream market-data provider.

    Infrastructure adapters catch provider-specific exceptions and translate
    them into subclasses of this error, so the application layer remains
    independent of Yahoo Finance or any future provider.
    """

    def __init__(self, message: str, *, provider_name: str) -> None:
        self.provider_name = provider_name
        super().__init__(f"[{provider_name}] {message}")


class ProviderTimeoutError(ProviderError):
    """Raised when a provider request does not complete within its timeout."""


class ProviderUnavailableError(ProviderError):
    """
    Raised when the provider cannot be reached or is temporarily unavailable.

    This remains separate from rate limiting because callers may handle the
    two conditions differently.
    """


class ProviderRateLimitedError(ProviderError):
    """
    Raised when the upstream provider reports that its rate limit was exceeded.

    Attributes:
        retry_after_seconds: Provider-suggested delay before retrying, when
            available. None means the provider did not supply a delay.

    Raises:
        ValueError: If retry_after_seconds is negative.
    """

    def __init__(
        self,
        message: str,
        *,
        provider_name: str,
        retry_after_seconds: int | None = None,
    ) -> None:
        if retry_after_seconds is not None and retry_after_seconds < 0:
            raise ValueError("retry_after_seconds cannot be negative")

        self.retry_after_seconds = retry_after_seconds
        super().__init__(message, provider_name=provider_name)


class InvalidQuoteDataError(ProviderError):
    """
    Raised when a provider responds successfully but returns unusable data.

    Examples include missing price fields, invalid numeric values, or an
    unexpected payload shape.
    """

    def __init__(
        self,
        message: str,
        *,
        provider_name: str,
        symbol: IndexSymbol | str | None = None,
    ) -> None:
        self.symbol = symbol
        super().__init__(message, provider_name=provider_name)