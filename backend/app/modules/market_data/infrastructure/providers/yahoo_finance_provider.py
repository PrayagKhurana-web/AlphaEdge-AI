"""
Yahoo Finance implementation of MarketDataProviderPort.

This is the only file in the market_data module that knows Yahoo Finance's
endpoint URL(s), request/response shape, or field names -- every other
layer depends solely on MarketDataProviderPort and this module's own
domain entities/exceptions. Swapping to a different upstream provider
later means adding a new class here that satisfies the same port; it
requires no change to application/services.py or the API layer.

Endpoint note: this adapter uses Yahoo Finance's chart endpoint
(/v8/finance/chart/{symbol}) rather than the batch quote endpoint
(/v7/finance/quote), because the batch endpoint now returns HTTP 401 for
unauthenticated callers. The chart endpoint accepts exactly one symbol per
request, so get_quotes() fetches all requested symbols concurrently via
asyncio.gather rather than in a single batched call.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Final, NoReturn
from urllib.parse import quote

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

# Yahoo Finance's per-symbol chart endpoint. Kept private to this adapter
# -- no other file in the codebase should ever reference this URL.
_CHART_ENDPOINT_URL_TEMPLATE: Final[str] = (
    "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
)
_CHART_QUERY_PARAMS: Final[dict[str, str]] = {"interval": "1m", "range": "1d"}

# A browser-like User-Agent is required; Yahoo's endpoints reject requests
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


class YahooFinanceProvider(MarketDataProviderPort):
    """
    MarketDataProviderPort implementation backed by Yahoo Finance's public
    per-symbol chart endpoint, accessed directly over HTTP (no yfinance
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
        exactly one code path that talks to Yahoo Finance and exactly one
        place error-priority selection is implemented.

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
        quote_value = quotes.get(symbol)
        if quote_value is None:
            raise InvalidQuoteDataError(
                f"No valid quote data was returned for symbol {symbol!r}.",
                provider_name=type(self).__name__,
                symbol=symbol,
            )
        return quote_value

    async def get_quotes(
        self, symbols: Sequence[IndexSymbol]
    ) -> Mapping[IndexSymbol, IndexQuote]:
        """
        Fetches quotes for multiple indices concurrently, one HTTP request
        per symbol (the chart endpoint does not support batching), via
        asyncio.gather(..., return_exceptions=True).

        See MarketDataProviderPort.get_quotes for the full contract this
        method must honor; this implementation follows it exactly:
        unsupported symbols raise SymbolNotFoundError before any HTTP call
        is made, a single symbol's failure never discards other symbols'
        successful quotes, and if every requested symbol fails, one
        aggregate domain exception is raised, chosen by priority
        (rate limit > timeout > unavailable > invalid data) among the
        collected per-symbol failures.

        Cancellation safety: if any child task's result is an
        asyncio.CancelledError (i.e. that task was cancelled -- typically
        because the surrounding request/task was itself cancelled),
        cancellation is re-raised immediately rather than being treated as
        an ordinary provider failure or folded into InvalidQuoteDataError.
        Swallowing a CancelledError here would break the surrounding
        task's ability to actually stop.
        """
        if not symbols:
            return {}

        unique_symbols = list(dict.fromkeys(symbols))
        self._validate_all_supported(unique_symbols)

        fetch_tasks = [
            self._fetch_quote_for_symbol(symbol, _SYMBOL_TO_YAHOO[symbol])
            for symbol in unique_symbols
        ]
        results = await asyncio.gather(*fetch_tasks, return_exceptions=True)

        quotes: dict[IndexSymbol, IndexQuote] = {}
        failures: list[Exception] = []
        for symbol, result in zip(unique_symbols, results):
            if isinstance(result, asyncio.CancelledError):
                # Cancellation must propagate, never be treated as a
                # provider failure or converted into a domain exception.
                raise result
            if isinstance(result, IndexQuote):
                quotes[symbol] = result
                continue
            if isinstance(result, Exception):
                logger.warning(
                    "market_data: failed to fetch quote for %r: %s",
                    symbol,
                    result,
                )
                failures.append(result)
                continue
            # Defensive fallback: some other BaseException subtype that is
            # neither CancelledError nor a plain Exception. This should not
            # occur in practice, since _fetch_quote_for_symbol only raises
            # this module's own Exception-derived domain exceptions, but
            # this branch avoids ever treating an unrecognized
            # BaseException as an ordinary failure without accounting for
            # it explicitly.
            logger.warning(
                "market_data: unexpected failure type for symbol %r: %s",
                symbol,
                type(result).__name__,
            )
            failures.append(
                InvalidQuoteDataError(
                    f"Unexpected failure type {type(result).__name__!r} "
                    f"while fetching symbol {symbol!r}.",
                    provider_name=type(self).__name__,
                    symbol=symbol,
                )
            )

        if quotes:
            return quotes

        self._raise_aggregate_error(failures, unique_symbols)

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

    def _raise_aggregate_error(
        self, failures: list[Exception], symbols: Sequence[IndexSymbol]
    ) -> NoReturn:
        """
        Raises a single representative domain exception when every
        requested symbol has failed, chosen by priority among the
        collected per-symbol failures: a rate limit takes precedence over
        a timeout, which takes precedence over a general unavailability,
        which takes precedence over an invalid-data failure. Falls back to
        a fresh InvalidQuoteDataError if no recognized domain exception
        type is present among the failures.
        """
        for failure in failures:
            if isinstance(failure, ProviderRateLimitedError):
                raise failure
        for failure in failures:
            if isinstance(failure, ProviderTimeoutError):
                raise failure
        for failure in failures:
            if isinstance(failure, ProviderUnavailableError):
                raise failure
        for failure in failures:
            if isinstance(failure, InvalidQuoteDataError):
                raise failure
        raise InvalidQuoteDataError(
            f"No valid quotes could be retrieved for requested symbols: "
            f"{list(symbols)!r}.",
            provider_name=type(self).__name__,
        )

    async def _fetch_quote_for_symbol(
        self, index_symbol: IndexSymbol, yahoo_symbol: str
    ) -> IndexQuote:
        """
        Issues one HTTP request to the chart endpoint for `yahoo_symbol`
        and parses the result into an IndexQuote, with every failure mode
        translated into this module's domain exceptions.

        Raises:
            ProviderTimeoutError: if the request did not complete within
                `request_timeout_seconds`.
            ProviderRateLimitedError: if Yahoo responds with HTTP 429.
            ProviderUnavailableError: if Yahoo responds with HTTP 401,
                403, or 5xx, or the request fails at the connection/
                transport level.
            InvalidQuoteDataError: if Yahoo responds successfully but the
                body is malformed, reports a chart-level error, is missing
                the expected result/meta structure, is missing required
                fields, contains values that cannot be parsed, has a zero
                previous close, or has an unusable timestamp.
        """
        encoded_symbol = quote(yahoo_symbol, safe="")
        url = _CHART_ENDPOINT_URL_TEMPLATE.format(symbol=encoded_symbol)

        try:
            response = await self._http_client.get(
                url,
                params=_CHART_QUERY_PARAMS,
                headers=_REQUEST_HEADERS,
                timeout=self._request_timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(
                f"Request to Yahoo Finance timed out after "
                f"{self._request_timeout_seconds} second(s) for symbol "
                f"{yahoo_symbol!r}.",
                provider_name=type(self).__name__,
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(
                f"Request to Yahoo Finance failed at the transport level "
                f"for symbol {yahoo_symbol!r}: {exc}",
                provider_name=type(self).__name__,
            ) from exc

        if response.status_code == 429:
            raise ProviderRateLimitedError(
                "Yahoo Finance reported rate limiting (HTTP 429).",
                provider_name=type(self).__name__,
                retry_after_seconds=self._parse_retry_after(response),
            )
        if response.status_code in (401, 403):
            raise ProviderUnavailableError(
                f"Yahoo Finance denied access (HTTP {response.status_code}).",
                provider_name=type(self).__name__,
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
                symbol=index_symbol,
            )

        return self._parse_chart_response(index_symbol, yahoo_symbol, response)

    def _parse_retry_after(self, response: httpx.Response) -> int | None:
        """
        Parses a numeric `Retry-After` header value in seconds, if present,
        well-formed, and non-negative. Returns None otherwise -- a missing,
        malformed, or negative value is treated as "unknown," never passed
        on to callers as a negative number.
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

    def _parse_chart_response(
        self,
        index_symbol: IndexSymbol,
        yahoo_symbol: str,
        response: httpx.Response,
    ) -> IndexQuote:
        """
        Parses a chart-endpoint JSON body for one symbol into an
        IndexQuote.

        Reads `chart.result[0].meta` for `regularMarketPrice`,
        `regularMarketTime`, `shortName`/`longName`, and a previous-close
        value (`chartPreviousClose`, falling back to `previousClose`).
        `change` and `change_percent` are always computed from
        `regularMarketPrice` and the previous close (never taken directly
        from a provider-supplied change field), so the response is
        internally consistent.

        Raises:
            InvalidQuoteDataError: for a malformed body, a chart-level
                error, a missing result/meta structure, missing required
                fields, unparseable numeric values, a zero previous close,
                or an unusable timestamp.
        """
        body = self._parse_json_body(response, symbol=index_symbol)

        chart = body.get("chart") if isinstance(body, dict) else None
        if not isinstance(chart, dict):
            raise InvalidQuoteDataError(
                "Yahoo Finance chart response was missing the expected "
                "'chart' object.",
                provider_name=type(self).__name__,
                symbol=index_symbol,
            )

        chart_error = chart.get("error")
        if chart_error:
            raise InvalidQuoteDataError(
                f"Yahoo Finance chart response reported an error: {chart_error!r}",
                provider_name=type(self).__name__,
                symbol=index_symbol,
            )

        result_list = chart.get("result")
        if not isinstance(result_list, list) or not result_list:
            raise InvalidQuoteDataError(
                "Yahoo Finance chart response did not contain a usable "
                "'result' list.",
                provider_name=type(self).__name__,
                symbol=index_symbol,
            )

        first_result = result_list[0]
        if not isinstance(first_result, dict):
            raise InvalidQuoteDataError(
                "Yahoo Finance chart response's first result entry was "
                "not a usable object.",
                provider_name=type(self).__name__,
                symbol=index_symbol,
            )

        meta = first_result.get("meta")
        if not isinstance(meta, dict):
            raise InvalidQuoteDataError(
                "Yahoo Finance chart response result was missing the "
                "expected 'meta' object.",
                provider_name=type(self).__name__,
                symbol=index_symbol,
            )

        regular_price = self._to_decimal(
            meta.get("regularMarketPrice"), symbol=index_symbol, field_name="regularMarketPrice"
        )

        previous_close_raw = meta.get("chartPreviousClose")
        if previous_close_raw is None:
            previous_close_raw = meta.get("previousClose")
        previous_close = self._to_decimal(
            previous_close_raw, symbol=index_symbol, field_name="chartPreviousClose/previousClose"
        )

        if previous_close == Decimal("0"):
            raise InvalidQuoteDataError(
                "Yahoo Finance chart response reported a zero previous "
                "close, which cannot be used to compute change percent.",
                provider_name=type(self).__name__,
                symbol=index_symbol,
            )

        change = regular_price - previous_close
        change_percent = (change / previous_close) * Decimal("100")

        as_of = self._to_utc_datetime(meta.get("regularMarketTime"), symbol=index_symbol)
        display_name = self._resolve_display_name(meta, fallback=yahoo_symbol)

        return IndexQuote(
            symbol=index_symbol,
            display_name=display_name,
            price=regular_price,
            change=change,
            change_percent=change_percent,
            as_of=as_of,
        )

    def _parse_json_body(
        self, response: httpx.Response, *, symbol: IndexSymbol
    ) -> dict[str, Any]:
        """
        Parses the response body as JSON.

        Raises:
            InvalidQuoteDataError: if the body is not valid JSON.
        """
        try:
            return response.json()
        except ValueError as exc:
            raise InvalidQuoteDataError(
                "Yahoo Finance response body was not valid JSON.",
                provider_name=type(self).__name__,
                symbol=symbol,
            ) from exc

    def _resolve_display_name(self, meta: dict[str, Any], *, fallback: str) -> str:
        """
        Resolves a human-readable display name for a quote: prefers
        `shortName` when it is a non-empty string, falls back to
        `longName` when *that* is a non-empty string, and otherwise falls
        back to the raw Yahoo symbol.
        """
        short_name = meta.get("shortName")
        if isinstance(short_name, str) and short_name.strip():
            return short_name

        long_name = meta.get("longName")
        if isinstance(long_name, str) and long_name.strip():
            return long_name

        return fallback

    def _to_decimal(
        self,
        raw_value: Any,
        *,
        symbol: IndexSymbol,
        field_name: str,
    ) -> Decimal:
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
                f"Expected numeric field {field_name!r} was missing.",
                provider_name=type(self).__name__,
                symbol=symbol,
            )
        try:
            decimal_value = Decimal(str(raw_value))
        except InvalidOperation as exc:
            raise InvalidQuoteDataError(
                f"Field {field_name!r} value {raw_value!r} could not be "
                "converted to Decimal.",
                provider_name=type(self).__name__,
                symbol=symbol,
            ) from exc

        if not decimal_value.is_finite():
            raise InvalidQuoteDataError(
                f"Field {field_name!r} value {raw_value!r} converted to a "
                "non-finite Decimal (NaN or Infinity), which is not a "
                "usable quote value.",
                provider_name=type(self).__name__,
                symbol=symbol,
            )

        return decimal_value

    def _to_utc_datetime(self, raw_value: Any, *, symbol: IndexSymbol) -> datetime:
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
                symbol=symbol,
            )
        try:
            unix_seconds = int(raw_value)
        except (TypeError, ValueError) as exc:
            raise InvalidQuoteDataError(
                f"'regularMarketTime' value {raw_value!r} is not a valid "
                "Unix timestamp.",
                provider_name=type(self).__name__,
                symbol=symbol,
            ) from exc

        try:
            return datetime.fromtimestamp(unix_seconds, tz=timezone.utc)
        except (OverflowError, OSError, ValueError) as exc:
            raise InvalidQuoteDataError(
                f"'regularMarketTime' value {unix_seconds!r} could not be "
                "converted to a datetime.",
                provider_name=type(self).__name__,
                symbol=symbol,
            ) from exc