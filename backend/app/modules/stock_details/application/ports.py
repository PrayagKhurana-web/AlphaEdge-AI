"""
Application-layer port (abstract interface) for the stock_details module.

A "port" here is a contract the application layer depends on but does not
implement -- concrete implementations live in infrastructure/ and are
wired in via dependency injection. This is what lets the quote backend
(Yahoo Finance today, or a future replacement) change without any change
to application/services.py or the API routes that depend on it.

An ABC is used here, for consistency with market_data's
MarketDataProviderPort/MarketDataCachePort and stock_search's
StockSearchProviderPort.

Per PROJECT_CONTEXT.md's Clean Architecture rule, this file may import
from domain/ (entities, exceptions) but must never import FastAPI,
Pydantic, httpx, a database driver, a concrete provider, configuration, or
anything from the stock_search or market_data modules' application or
infrastructure layers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.modules.stock_details.domain.entities import StockQuote
from app.modules.stock_details.domain.exceptions import (  # noqa: F401 -- referenced in docstrings
    InvalidQuoteDataError,
    QuoteProviderRateLimitedError,
    QuoteProviderTimeoutError,
    QuoteProviderUnavailableError,
)


class StockQuoteProviderPort(ABC):
    """
    Abstract contract for any backend capable of fetching a single
    stock's current quote.

    Concrete implementations are responsible for translating their own
    backend's responses and errors into this module's domain exceptions
    (QuoteProviderTimeoutError, QuoteProviderRateLimitedError,
    QuoteProviderUnavailableError, InvalidQuoteDataError) -- callers of
    this port should never need to catch a provider-specific exception
    type.
    """

    @abstractmethod
    async def get_quote(self, display_symbol: str) -> StockQuote:
        """
        Fetches the current quote for the stock identified by
        `display_symbol`.

        Args:
            display_symbol: The UI-facing presentation identifier (e.g.
                "RELIANCE.NSE") for the stock to fetch. Callers of this
                port (the application layer) are responsible for
                normalizing and validating this value -- e.g. stripping
                whitespace, rejecting empty or malformed identifiers --
                before calling this method, per the domain exception
                defined for that purpose (InvalidDisplaySymbolError).
                Implementations are not required to re-validate
                `display_symbol` against those rules.

        Returns:
            Exactly one StockQuote for the requested stock.

        Raises:
            QuoteProviderTimeoutError: if the backend did not respond in
                time.
            QuoteProviderRateLimitedError: if the backend reports its
                rate limit has been exceeded.
            QuoteProviderUnavailableError: if the backend could not be
                reached or reported an outage.
            InvalidQuoteDataError: if the backend responded but its data
                could not be converted into a valid StockQuote.
        """
        raise NotImplementedError