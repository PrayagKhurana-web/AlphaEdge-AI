# backend/app/modules/stock_details/application/services.py
"""
Application-layer use case for fetching a single stock's current quote.

This module contains the orchestration logic that validates and
normalizes a caller-supplied display symbol and delegates to the injected
StockQuoteProviderPort -- per PROJECT_CONTEXT.md's Clean Architecture
rule, it depends only on application/ports.py and domain/entities.py +
domain/exceptions.py, never on FastAPI, Pydantic, httpx, a database
driver, or any concrete provider implementation.

This layer owns all display-symbol validation; providers assume they are
only ever called with an already-validated, well-formed display symbol
and are not required to re-validate it.
"""

from __future__ import annotations

import re

from app.modules.stock_details.application.ports import StockQuoteProviderPort
from app.modules.stock_details.domain.entities import StockQuote
from app.modules.stock_details.domain.exceptions import InvalidDisplaySymbolError

# Supported display symbol format: "<SYMBOL>.<EXCHANGE>", exactly one dot,
# a non-empty symbol with no internal whitespace, and an exchange that is
# exactly "NSE" or "BSE" (case-sensitive, matching the exact string this
# module accepts as a valid exchange token in a display symbol).
_DISPLAY_SYMBOL_PATTERN = re.compile(r"^(?P<symbol>\S+)\.(?P<exchange>NSE|BSE)$")


class StockQuoteService:
    """
    Use case: validate and normalize a caller-supplied display symbol,
    then return the current StockQuote for it via the injected
    StockQuoteProviderPort.

    This service is the only place in the module that decides what counts
    as a valid display symbol -- the provider implementation is only ever
    asked to fetch a quote for an already-validated, well-formed display
    symbol, and is never expected to perform this validation itself.
    """

    def __init__(self, provider: StockQuoteProviderPort) -> None:
        """
        Args:
            provider: Quote backend, satisfying StockQuoteProviderPort.
        """
        self._provider = provider

    async def get_quote(self, display_symbol: str) -> StockQuote:
        """
        Validates `display_symbol` and returns the current StockQuote for
        it, fetched via the injected provider.

        Args:
            display_symbol: Raw, caller-supplied display symbol in the
                form "SYMBOL.EXCHANGE" (e.g. "RELIANCE.NSE").

        Returns:
            The StockQuote returned by the provider, unchanged -- this
            method does not modify, recompute, or otherwise alter any
            field of the result.

        Raises:
            InvalidDisplaySymbolError: if `display_symbol` is empty (after
                stripping whitespace) or does not match the supported
                "SYMBOL.EXCHANGE" format (exactly one dot, a non-empty
                symbol with no internal whitespace, and an exchange of
                either "NSE" or "BSE").
            QuoteProviderTimeoutError, QuoteProviderRateLimitedError,
            QuoteProviderUnavailableError, InvalidQuoteDataError:
                propagated unchanged from the provider.
        """
        normalized_display_symbol = self._normalize_display_symbol(display_symbol)
        self._validate_display_symbol(normalized_display_symbol)

        return await self._provider.get_quote(normalized_display_symbol)

    def _normalize_display_symbol(self, display_symbol: str) -> str:
        """
        Strips leading/trailing whitespace from `display_symbol` and
        uppercases the result.

        Uppercasing here canonicalizes the symbol the same way
        stock_search.infrastructure.providers.yahoo_search_provider.
        YahooStockSearchProvider._normalize_symbol already does (".strip()
        .upper()"), so a stock's canonical identifier is represented
        identically regardless of whether it was resolved via search or
        requested directly for a quote. Without this, a lowercase or
        mixed-case request (e.g. "reliance.NSE") would previously produce
        a StockQuote.symbol of "reliance" instead of "RELIANCE", diverging
        from stock_search's StockSearchResult.symbol for the same stock.
        """
        return display_symbol.strip().upper()

    def _validate_display_symbol(self, normalized_display_symbol: str) -> None:
        """
        Validates that `normalized_display_symbol` is non-empty and
        matches the supported "SYMBOL.EXCHANGE" format.

        Raises:
            InvalidDisplaySymbolError: if the display symbol is empty, if
                it does not contain exactly one dot, if the symbol portion
                is empty or contains whitespace, or if the exchange
                portion is not exactly "NSE" or "BSE".
        """
        if not normalized_display_symbol:
            raise InvalidDisplaySymbolError(
                normalized_display_symbol,
                reason="display symbol must not be empty",
            )

        if normalized_display_symbol.count(".") != 1:
            raise InvalidDisplaySymbolError(
                normalized_display_symbol,
                reason="display symbol must contain exactly one dot in the form SYMBOL.EXCHANGE",
            )

        match = _DISPLAY_SYMBOL_PATTERN.match(normalized_display_symbol)
        if match is None:
            raise InvalidDisplaySymbolError(
                normalized_display_symbol,
                reason=(
                    "display symbol must be in the form SYMBOL.EXCHANGE, "
                    "with a non-empty symbol containing no whitespace and "
                    "an exchange of either NSE or BSE"
                ),
            )