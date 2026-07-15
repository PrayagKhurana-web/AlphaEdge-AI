"""
Yahoo Finance implementation of MarketDataProviderPort.

This is the only file in the market_data module that knows Yahoo Finance's
quote endpoint URL, its request/response shape, or its field names --
every other layer depends solely on MarketDataProviderPort and this
module's own domain entities/exceptions. Swapping to a different upstream
provider later means adding a new class here that satisfies the same port;
it requires no change to application/services.py or the API layer.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Final

import httpx

from app.modules.market_data.application.ports import MarketDataProviderPort
from app.modules.market_data.domain.entities import IndexQuote, IndexSymbol
from app.modules.market_data.domain.exceptions import (
    InvalidQuoteDataError,
    ProviderRateLimitedError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    SymbolNotFoundError,
)

logger = logging.getLogger(__name__)

# Yahoo Finance's batch quote endpoint. Kept private to this adapter --
# no other file in the codebase should ever reference this URL.
_QUOTE_ENDPOINT_URL: Final[str] = "https://query1.finance.yahoo.com/v7/finance/quote"

# A browser-like User-Agent is required; Yahoo's endpoint rejects requests
# that look like a bare script client.
_REQUEST_HEADERS: Final[dict[str, str]] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

# Provider-specific symbol mapping, kept private to this adapter per the
# sprint requirement that provider-symbol mapping never leaks outside it.
_SYMBOL_TO_YAHOO: Final[dict[IndexSymbol, str]] = {
    IndexSymbol.NIFTY_50: "^NSEI",
    IndexSymbol.SENSEX: "^BSESN",
    IndexSymbol.BANK_NIFTY: "^NSEBANK",
    IndexSymbol.INDIA_VIX: "^INDIAVIX",
}
_YAHOO_TO_SYMBOL: Final[dict[str, IndexSymbol]] = {
    yahoo_symbol: index_symbol for index_symbol, yahoo_symbol in _SYMBOL_TO_YAHOO.items()
}


class YahooFinanceProvider(MarketDataProviderPort):
    """
    MarketDataProviderPort implementation backed by Yahoo Finance's public
    batch quote endpoint, accessed directly over HTTP (no yfinance
    dependency).

    A single httpx.AsyncClient is injected via the constructor and reused
    across calls, so connection pooling/keep-alive is handled by the
    caller's client configuration rather than by this class -- this class
    never constructs its own client.
    """

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        request_timeout_seconds: float,
    ) -> None:
        """
        Args:
            http_client: A shared httpx.AsyncClient instance to issue
                requests through.
            request_timeout_seconds: Per-request timeout, in seconds. Must
                be strictly positive.

        Raises:
            ValueError: if `request_timeout_seconds` is less than or equal
                to zero.
        """
        if request_timeout_seconds <= 0:
            raise ValueError(
                "request_timeout_seconds must be strictly positive, got "
                f"{request_timeout_seconds!r}"
            )
        self._http_client = http_client
        self._request_timeout_seconds = request_timeout_seconds

    async def get_quote(self, symbol: IndexSymbol) -> IndexQuote:
        """
        Fetches a single index's current quote.

        Delegates to get_quotes() with a single-element list so there is
        exactly one code path that talks to Yahoo Finance.

        Raises:
            SymbolNotFoundError: if `symbol` is not in this adapter's
                symbol mapping.
            ProviderTimeoutError, ProviderRateLimitedError,
            ProviderUnavailableError: on the corresponding upstream
                failure.
            InvalidQuoteDataError: if the upstream response could not be
                parsed into a valid quote for this symbol.
        """
        quotes = await self.get_quotes([symbol])
        quote = quotes.get(symbol)
        if quote is None:
            raise InvalidQuoteDataError(
                f"No valid quote data was returned for symbol {symbol!r}.",
                provider_name=type(self).__name__,
                symbol=symbol,
            )
        return quote

    async def get_quotes(
        self, symbols: Sequence[IndexSymbol]
    ) -> Mapping[IndexSymbol, IndexQuote]:
        """
        Fetches quotes for multiple indices in a single batched request to
        Yahoo Finance's quote endpoint, which accepts a comma-separated
        `symbols` query parameter and returns all of them in one response.

        See MarketDataProviderPort.get_quotes for the full contract this
        method must honor; this implementation follows it exactly:
        unsupported symbols raise SymbolNotFoundError before any HTTP call
        is made, transport-level failures raise the corresponding
        ProviderError subclass, and per-symbol parsing failures are
        omitted from the result unless every requested symbol fails to
        parse, in which case InvalidQuoteDataError is raised. Only symbols
        that were actually requested can appear in the returned mapping --
        any unrelated entry Yahoo might include in its response is
        discarded.
        """
        if not symbols:
            return {}

        requested_symbols = frozenset(symbols)
        unique_symbols = list(dict.fromkeys(symbols))
        self._validate_all_supported(unique_symbols)

        yahoo_symbols = [_SYMBOL_TO_YAHOO[symbol] for symbol in unique_symbols]
        raw_results = await self._fetch_raw_quotes(yahoo_symbols)

        quotes: dict[IndexSymbol, IndexQuote] = {}
        for raw_quote in raw_results:
            parsed = self._try_parse_quote(raw_quote)
            if parsed is None:
                continue
            index_symbol, quote = parsed
            # Defense in depth: only keep entries for symbols that were
            # actually requested, even though _YAHOO_TO_SYMBOL should
            # already guarantee this -- an unrequested index must never
            # leak into the result.
            if index_symbol in requested_symbols:
                quotes[index_symbol] = quote

        if not quotes:
            raise InvalidQuoteDataError(
                "No valid quotes could be parsed from the provider response "
                f"for requested symbols: {unique_symbols!r}.",
                provider_name=type(self).__name__,
            )

        return quotes

    def _validate_all_supported(self, symbols: Sequence[IndexSymbol]) -> None:
        """
        Raises SymbolNotFoundError for the first requested symbol this
        adapter has no Yahoo Finance mapping for. Called before any HTTP
        request is made, so an unsupported symbol never costs a network
        call.
        """
        for symbol in symbols:
            if symbol not in _SYMBOL_TO_YAHOO:
                raise SymbolNotFoundError(symbol)

    async def _fetch_raw_quotes(self, yahoo_symbols: Sequence[str]) -> list[dict[str, Any]]:
        """
        Issues the batched HTTP request to Yahoo Finance and returns the
        raw `quoteResponse.result` list, with every failure mode
        translated into this module's domain exceptions.

        Raises:
            ProviderTimeoutError: if the request did not complete within
                `request_timeout_seconds`.
            ProviderRateLimitedError: if Yahoo responds with HTTP 429.
            ProviderUnavailableError: if Yahoo responds with HTTP 5xx, or
                the request fails at the connection/transport level.
            InvalidQuoteDataError: if Yahoo responds successfully but the
                body is not valid JSON, does not contain the expected
                `quoteResponse.result` structure, or responds with an
                unexpected non-429 4xx status.
        """
        try:
            response = await self._http_client.get(
                _QUOTE_ENDPOINT_URL,
                params={"symbols": ",".join(yahoo_symbols)},
                headers=_REQUEST_HEADERS,
                timeout=self._request_timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(
                f"Request to Yahoo Finance timed out after "
                f"{self._request_timeout_seconds} second(s).",
                provider_name=type(self).__name__,
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(
                f"Request to Yahoo Finance failed at the transport level: {exc}",
                provider_name=type(self).__name__,
            ) from exc

        if response.status_code == 429:
            raise ProviderRateLimitedError(
                "Yahoo Finance reported rate limiting (HTTP 429).",
                provider_name=type(self).__name__,
                retry_after_seconds=self._parse_retry_after(response),
            )
        if response.status_code >= 500:
            raise ProviderUnavailableError(
                f"Yahoo Finance returned server error HTTP {response.status_code}.",
                provider_name=type(self).__name__,
            )
        if response.status_code >= 400:
            raise InvalidQuoteDataError(
                f"Yahoo Finance returned unexpected client error "
                f"HTTP {response.status_code}.",
                provider_name=type(self).__name__,
            )

        return self._extract_result_list(response)

    def _parse_retry_after(self, response: httpx.Response) -> int | None:
        """
        Parses a numeric `Retry-After` header value in seconds, if present,
        well-formed, and non-negative.

        Returns None if the header is absent, is not a plain integer
        (Yahoo does not document HTTP-date-formatted values for this
        endpoint, so that format is not handled here), or is negative --
        a negative retry-after value is meaningless and must never be
        passed on to callers.
        """
        raw_value = response.headers.get("Retry-After")
        if raw_value is None:
            return None
        try:
            parsed_value = int(raw_value)
        except ValueError:
            return None
        if parsed_value < 0:
            return None
        return parsed_value

    def _extract_result_list(self, response: httpx.Response) -> list[dict[str, Any]]:
        """
        Parses the response body as JSON and returns the
        `quoteResponse.result` list, filtered to only the entries that are
        themselves dicts.

        Raises:
            InvalidQuoteDataError: if the body is not valid JSON, the
                expected `quoteResponse.result` list is missing or is not
                a list, or the list is non-empty but contains no dict
                entries at all (i.e. every entry is a malformed,
                unusable shape).
        """
        try:
            body = response.json()
        except ValueError as exc:
            raise InvalidQuoteDataError(
                "Yahoo Finance response body was not valid JSON.",
                provider_name=type(self).__name__,
            ) from exc

        quote_response = body.get("quoteResponse") if isinstance(body, dict) else None
        result_list = quote_response.get("result") if isinstance(quote_response, dict) else None

        if not isinstance(result_list, list):
            raise InvalidQuoteDataError(
                "Yahoo Finance response did not contain the expected "
                "'quoteResponse.result' list.",
                provider_name=type(self).__name__,
            )

        dict_entries: list[dict[str, Any]] = []
        for entry in result_list:
            if isinstance(entry, dict):
                dict_entries.append(entry)
            else:
                logger.warning(
                    "Yahoo Finance response contained a non-dict result "
                    "entry and it was discarded: %r",
                    entry,
                )

        if result_list and not dict_entries:
            raise InvalidQuoteDataError(
                "Yahoo Finance response 'quoteResponse.result' contained "
                "no usable (dict) entries.",
                provider_name=type(self).__name__,
            )

        return dict_entries

    def _try_parse_quote(self, raw_quote: dict[str, Any]) -> tuple[IndexSymbol, IndexQuote] | None:
        """
        Attempts to parse one raw result entry into an (IndexSymbol,
        IndexQuote) pair.

        Returns None (rather than raising) for any entry that cannot be
        parsed -- an unrecognized Yahoo symbol, a missing required field,
        or an unusable numeric/timestamp value -- so that one bad entry in
        an otherwise valid batch response does not prevent the other
        entries from being returned. The failure is logged for
        diagnostics.
        """
        yahoo_symbol = raw_quote.get("symbol")
        index_symbol = _YAHOO_TO_SYMBOL.get(yahoo_symbol) if isinstance(yahoo_symbol, str) else None
        if index_symbol is None:
            logger.warning(
                "Yahoo Finance response contained an unrecognized symbol: %r",
                yahoo_symbol,
            )
            return None

        try:
            price = self._to_decimal(raw_quote.get("regularMarketPrice"))
            change = self._to_decimal(raw_quote.get("regularMarketChange"))
            change_percent = self._to_decimal(raw_quote.get("regularMarketChangePercent"))
            as_of = self._to_utc_datetime(raw_quote.get("regularMarketTime"))
        except InvalidQuoteDataError as exc:
            logger.warning(
                "Failed to parse Yahoo Finance quote for %r: %s", index_symbol, exc
            )
            return None

        display_name = self._resolve_display_name(raw_quote, fallback=yahoo_symbol)

        quote = IndexQuote(
            symbol=index_symbol,
            display_name=display_name,
            price=price,
            change=change,
            change_percent=change_percent,
            as_of=as_of,
        )
        return index_symbol, quote

    def _resolve_display_name(self, raw_quote: dict[str, Any], *, fallback: str) -> str:
        """
        Resolves a human-readable display name for a quote: prefers
        `shortName` when it is a non-empty string, falls back to
        `longName` when *that* is a non-empty string, and otherwise falls
        back to the raw Yahoo symbol.
        """
        short_name = raw_quote.get("shortName")
        if isinstance(short_name, str) and short_name.strip():
            return short_name

        long_name = raw_quote.get("longName")
        if isinstance(long_name, str) and long_name.strip():
            return long_name

        return fallback

    def _to_decimal(self, raw_value: Any) -> Decimal:
        """
        Converts a raw numeric field to Decimal via str() (never via a
        direct float-to-Decimal construction, which would carry the
        source float's binary rounding error into the Decimal value).

        Raises:
            InvalidQuoteDataError: if `raw_value` is None, cannot be
                converted to a Decimal, or converts to a non-finite
                Decimal (NaN or Infinity) -- neither of which is a usable
                price/change value.
        """
        if raw_value is None:
            raise InvalidQuoteDataError(
                "Expected numeric field was missing.",
                provider_name=type(self).__name__,
            )
        try:
            decimal_value = Decimal(str(raw_value))
        except InvalidOperation as exc:
            raise InvalidQuoteDataError(
                f"Value {raw_value!r} could not be converted to Decimal.",
                provider_name=type(self).__name__,
            ) from exc

        if not decimal_value.is_finite():
            raise InvalidQuoteDataError(
                f"Value {raw_value!r} converted to a non-finite Decimal "
                "(NaN or Infinity), which is not a usable quote value.",
                provider_name=type(self).__name__,
            )

        return decimal_value

    def _to_utc_datetime(self, raw_value: Any) -> datetime:
        """
        Converts a Unix-epoch-seconds field (as returned by Yahoo's
        `regularMarketTime`) into a timezone-aware UTC datetime, matching
        IndexQuote.as_of's required format.

        Raises:
            InvalidQuoteDataError: if `raw_value` is missing, is not a
                valid integer, or does not represent a timestamp that
                Python's datetime can construct (e.g. out of range).
        """
        if raw_value is None:
            raise InvalidQuoteDataError(
                "Expected 'regularMarketTime' field was missing.",
                provider_name=type(self).__name__,
            )
        try:
            unix_seconds = int(raw_value)
        except (TypeError, ValueError) as exc:
            raise InvalidQuoteDataError(
                f"'regularMarketTime' value {raw_value!r} is not a valid "
                "Unix timestamp.",
                provider_name=type(self).__name__,
            ) from exc

        try:
            return datetime.fromtimestamp(unix_seconds, tz=timezone.utc)
        except (OverflowError, OSError, ValueError) as exc:
            raise InvalidQuoteDataError(
                f"'regularMarketTime' value {unix_seconds!r} could not be "
                "converted to a datetime.",
                provider_name=type(self).__name__,
            ) from exc