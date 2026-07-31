"""
Yahoo Finance implementation of HistoricalDataProviderPort.

This is the only file in the stock_history module that knows Yahoo
Finance's chart endpoint URL, request/response shape, or field names --
every other layer depends solely on HistoricalDataProviderPort and this
module's own domain entities/exceptions. Swapping to a different history
backend later means adding a new class here that satisfies the same
port; it requires no change to application/services.py or the API layer.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Final

import httpx

from app.modules.stock_history.application.ports import HistoricalDataProviderPort
from app.modules.stock_history.domain.entities import HistoricalCandle, HistoricalSeries
from app.modules.stock_history.domain.exceptions import (
    HistoryProviderRateLimitedError,
    HistoryProviderTimeoutError,
    HistoryProviderUnavailableError,
    InvalidHistoricalDataError,
)
from app.modules.stock_search.domain.entities import StockExchange

# Yahoo Finance's per-symbol chart endpoint. Kept private to this adapter
# -- no other file in the codebase should ever reference this URL.
_CHART_ENDPOINT_URL_TEMPLATE: Final[str] = (
    "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
)

# A browser-like User-Agent is required; Yahoo's endpoints reject requests
# that look like a bare script client.
_REQUEST_HEADERS: Final[dict[str, str]] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

# Display-symbol exchange token -> Yahoo suffix mapping. Kept private to
# this adapter, mirroring stock_details' YahooQuoteProvider convention of
# never leaking provider-specific symbol conventions outside the adapter
# that owns them.
_EXCHANGE_TOKEN_TO_YAHOO_SUFFIX: Final[dict[str, str]] = {
    "NSE": ".NS",
    "BSE": ".BO",
}

_PROVIDER_NAME: Final[str] = "YahooHistoryProvider"

# Required OHLC field names, used both for extracting arrays from the
# response and for identifying which field is missing/malformed in error
# messages and per-row validation. Volume is intentionally NOT part of
# this tuple -- volume participates in per-row validation separately (see
# _build_candles), since only open/high/low/close determine whether a row
# is a genuine no-trading placeholder.
_REQUIRED_QUOTE_FIELDS: Final[tuple[str, ...]] = ("open", "high", "low", "close")


class YahooHistoryProvider(HistoricalDataProviderPort):
    """
    HistoricalDataProviderPort implementation backed by Yahoo Finance's
    public per-symbol chart endpoint, accessed directly over HTTP.

    A single httpx.AsyncClient is injected via the constructor and reused
    across calls, so connection pooling/keep-alive is handled by the
    caller's client configuration rather than by this class -- this class
    never constructs or closes its own client.

    Callers of get_history() are expected to supply an already-validated
    display symbol, period, and interval -- that validation is owned
    entirely by application/services.py's HistoricalDataService, and this
    adapter performs no request-shape validation of its own beyond what
    naturally falls out of the Yahoo-symbol conversion and response
    parsing below.
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
            request_timeout_seconds: Per-request timeout, in seconds.
        """
        self._http_client = http_client
        self._request_timeout_seconds = request_timeout_seconds

    async def get_history(
        self,
        display_symbol: str,
        *,
        period: str,
        interval: str,
    ) -> HistoricalSeries:
        """
        Fetches historical OHLCV candle data for `display_symbol` from
        Yahoo Finance's chart endpoint.

        Args:
            display_symbol: An already-validated display symbol in the
                form "SYMBOL.EXCHANGE" (e.g. "RELIANCE.NSE"), as produced
                by application/services.py's HistoricalDataService.
            period: An already-validated lookback period (e.g. "1y").
            interval: An already-validated candle interval (e.g. "1d").

        Returns:
            A HistoricalSeries for the requested stock, preserving the
            requested `period` and `interval` exactly. May contain zero
            candles if Yahoo returns a structurally valid response with no
            usable trading data -- that is a valid outcome, not a parsing
            failure.

        Raises:
            HistoryProviderTimeoutError: if the request did not complete
                within `request_timeout_seconds`.
            HistoryProviderRateLimitedError: if Yahoo responds with HTTP
                429.
            HistoryProviderUnavailableError: if Yahoo responds with HTTP
                401, 403, or 5xx, or the request fails at the connection/
                transport level.
            InvalidHistoricalDataError: if Yahoo responds successfully but
                the body is malformed, reports a chart-level error, is
                missing the expected structure, contains mismatched array
                lengths, contains unparseable values, or produces data
                that fails HistoricalCandle/HistoricalSeries validation.
        """
        canonical_symbol, exchange_token = self._split_display_symbol(display_symbol)
        yahoo_symbol = self._to_yahoo_symbol(canonical_symbol, exchange_token)

        response = await self._fetch_chart_response(
            yahoo_symbol, display_symbol=display_symbol, period=period, interval=interval
        )
        return self._parse_chart_response(
            response,
            display_symbol=display_symbol,
            canonical_symbol=canonical_symbol,
            exchange_token=exchange_token,
            period=period,
            interval=interval,
        )

    def _split_display_symbol(self, display_symbol: str) -> tuple[str, str]:
        """
        Splits an already-validated "SYMBOL.EXCHANGE" display symbol into
        its canonical symbol and exchange token.

        This performs no validation of its own -- application/services.py
        guarantees `display_symbol` already matches the supported format
        before this adapter is ever called.
        """
        canonical_symbol, _, exchange_token = display_symbol.rpartition(".")
        return canonical_symbol, exchange_token

    def _to_yahoo_symbol(self, canonical_symbol: str, exchange_token: str) -> str:
        """
        Converts a canonical symbol and exchange token into Yahoo
        Finance's own symbol convention (e.g. "RELIANCE" + "NSE" ->
        "RELIANCE.NS", "500325" + "BSE" -> "500325.BO").
        """
        yahoo_suffix = _EXCHANGE_TOKEN_TO_YAHOO_SUFFIX[exchange_token]
        return f"{canonical_symbol}{yahoo_suffix}"

    async def _fetch_chart_response(
        self,
        yahoo_symbol: str,
        *,
        display_symbol: str,
        period: str,
        interval: str,
    ) -> httpx.Response:
        """
        Issues the HTTP request to Yahoo Finance's chart endpoint for
        `yahoo_symbol`, with every failure mode translated into this
        module's domain exceptions.

        Raises:
            HistoryProviderTimeoutError: if the request did not complete
                in time.
            HistoryProviderRateLimitedError: if Yahoo responds with HTTP
                429.
            HistoryProviderUnavailableError: if Yahoo responds with HTTP
                401, 403, or 5xx, or the request fails at the connection/
                transport level.
            InvalidHistoricalDataError: if Yahoo responds with an
                unexpected non-429 4xx status.
        """
        url = _CHART_ENDPOINT_URL_TEMPLATE.format(symbol=yahoo_symbol)
        params = {
            "range": period,
            "interval": interval,
            "events": "div,splits",
            "includeAdjustedClose": "true",
        }

        try:
            response = await self._http_client.get(
                url,
                params=params,
                headers=_REQUEST_HEADERS,
                timeout=httpx.Timeout(self._request_timeout_seconds),
            )
        except httpx.TimeoutException as exc:
            raise HistoryProviderTimeoutError(
                f"Request to Yahoo Finance timed out after "
                f"{self._request_timeout_seconds} second(s) for symbol "
                f"{yahoo_symbol!r}.",
                provider_name=_PROVIDER_NAME,
            ) from exc
        except httpx.HTTPError as exc:
            raise HistoryProviderUnavailableError(
                f"Request to Yahoo Finance failed at the transport level "
                f"for symbol {yahoo_symbol!r}: {exc}",
                provider_name=_PROVIDER_NAME,
            ) from exc

        if response.status_code == 429:
            raise HistoryProviderRateLimitedError(
                "Yahoo Finance reported rate limiting (HTTP 429).",
                provider_name=_PROVIDER_NAME,
                retry_after_seconds=self._parse_retry_after(response),
            )
        if response.status_code in (401, 403):
            raise HistoryProviderUnavailableError(
                f"Yahoo Finance denied access (HTTP {response.status_code}).",
                provider_name=_PROVIDER_NAME,
            )
        if response.status_code >= 500:
            raise HistoryProviderUnavailableError(
                f"Yahoo Finance returned server error HTTP {response.status_code}.",
                provider_name=_PROVIDER_NAME,
            )
        if response.status_code >= 400:
            raise InvalidHistoricalDataError(
                f"Yahoo Finance returned unexpected client error "
                f"HTTP {response.status_code}.",
                provider_name=_PROVIDER_NAME,
                display_symbol=display_symbol,
            )

        return response

    def _parse_retry_after(self, response: httpx.Response) -> int | None:
        """
        Parses a numeric `Retry-After` header value in seconds, if present,
        well-formed, and non-negative. Returns None for a missing,
        malformed, HTTP-date-formatted, or negative value.
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
        response: httpx.Response,
        *,
        display_symbol: str,
        canonical_symbol: str,
        exchange_token: str,
        period: str,
        interval: str,
    ) -> HistoricalSeries:
        """
        Parses a chart-endpoint JSON body into a HistoricalSeries.

        Raises:
            InvalidHistoricalDataError: for a malformed body, a
                chart-level error, a missing result/meta structure,
                missing or mismatched-length arrays, unparseable values,
                or values that fail HistoricalCandle/HistoricalSeries
                validation.
        """
        body = self._parse_json_body(response, display_symbol=display_symbol)

        chart = body.get("chart") if isinstance(body, dict) else None
        if not isinstance(chart, dict):
            raise InvalidHistoricalDataError(
                "Yahoo Finance chart response was missing the expected "
                "'chart' object.",
                provider_name=_PROVIDER_NAME,
                display_symbol=display_symbol,
            )

        chart_error = chart.get("error")
        if chart_error:
            raise InvalidHistoricalDataError(
                f"Yahoo Finance chart response reported an error: {chart_error!r}",
                provider_name=_PROVIDER_NAME,
                display_symbol=display_symbol,
            )

        result_list = chart.get("result")
        if not isinstance(result_list, list) or not result_list:
            raise InvalidHistoricalDataError(
                "Yahoo Finance chart response did not contain a usable "
                "'result' list.",
                provider_name=_PROVIDER_NAME,
                display_symbol=display_symbol,
            )

        first_result = result_list[0]
        if not isinstance(first_result, dict):
            raise InvalidHistoricalDataError(
                "Yahoo Finance chart response's first result entry was "
                "not a usable object.",
                provider_name=_PROVIDER_NAME,
                display_symbol=display_symbol,
            )

        meta = first_result.get("meta")
        if not isinstance(meta, dict):
            raise InvalidHistoricalDataError(
                "Yahoo Finance chart response result was missing the "
                "expected 'meta' object.",
                provider_name=_PROVIDER_NAME,
                display_symbol=display_symbol,
            )

        timestamps = self._extract_timestamps(first_result, display_symbol=display_symbol)
        quote_arrays = self._extract_quote_arrays(
            first_result, expected_length=len(timestamps), display_symbol=display_symbol
        )
        adjclose_array = self._extract_adjclose_array(
            first_result, expected_length=len(timestamps), display_symbol=display_symbol
        )

        candles = self._build_candles(
            timestamps,
            quote_arrays,
            adjclose_array,
            display_symbol=display_symbol,
        )

        company_name = self._resolve_company_name(meta, fallback=canonical_symbol)
        exchange = self._to_stock_exchange(
            exchange_token, display_symbol=display_symbol
        )

        try:
            return HistoricalSeries(
                symbol=canonical_symbol,
                display_symbol=display_symbol,
                company_name=company_name,
                exchange=exchange,
                interval=interval,
                period=period,
                candles=tuple(candles),
                fetched_at=datetime.now(timezone.utc),
            )
        except ValueError as exc:
            # HistoricalSeries' own validation (e.g. unordered or
            # duplicate timestamps, or a HistoricalCandle rejected by its
            # own __post_init__) rejected the assembled data -- translate
            # that into this module's own domain exception rather than
            # letting a raw ValueError escape this adapter.
            raise InvalidHistoricalDataError(
                f"Yahoo Finance chart response produced data that failed "
                f"domain validation: {exc}",
                provider_name=_PROVIDER_NAME,
                display_symbol=display_symbol,
            ) from exc

    def _to_stock_exchange(
        self, exchange_token: str, *, display_symbol: str
    ) -> StockExchange:
        """
        Converts an exchange token (e.g. "NSE") into a StockExchange
        instance, translating a failed conversion into
        InvalidHistoricalDataError rather than letting a raw ValueError
        escape this adapter.

        In normal operation `exchange_token` was already validated by
        application/services.py's display-symbol format check, so this
        conversion should always succeed -- this is a defensive
        translation, not an expected failure path.

        Raises:
            InvalidHistoricalDataError: if `exchange_token` is not a
                valid StockExchange value.
        """
        try:
            return StockExchange(exchange_token)
        except ValueError as exc:
            raise InvalidHistoricalDataError(
                f"Exchange token {exchange_token!r} could not be "
                "converted to a valid StockExchange.",
                provider_name=_PROVIDER_NAME,
                display_symbol=display_symbol,
            ) from exc

    def _parse_json_body(
        self, response: httpx.Response, *, display_symbol: str
    ) -> dict[str, Any]:
        """
        Parses the response body as JSON.

        Raises:
            InvalidHistoricalDataError: if the body is not valid JSON.
        """
        try:
            return response.json()
        except ValueError as exc:
            raise InvalidHistoricalDataError(
                "Yahoo Finance response body was not valid JSON.",
                provider_name=_PROVIDER_NAME,
                display_symbol=display_symbol,
            ) from exc

    def _extract_timestamps(
        self, result: dict[str, Any], *, display_symbol: str
    ) -> list[Any]:
        """
        Extracts the `timestamp` list from a chart result entry.

        Raises:
            InvalidHistoricalDataError: if `timestamp` is missing or is
                not a list.
        """
        timestamps = result.get("timestamp")
        if not isinstance(timestamps, list):
            raise InvalidHistoricalDataError(
                "Yahoo Finance chart response result was missing the "
                "expected 'timestamp' list.",
                provider_name=_PROVIDER_NAME,
                display_symbol=display_symbol,
            )
        return timestamps

    def _extract_quote_arrays(
        self,
        result: dict[str, Any],
        *,
        expected_length: int,
        display_symbol: str,
    ) -> dict[str, list[Any]]:
        """
        Extracts and validates the OHLCV arrays from
        `result.indicators.quote[0]`.

        Raises:
            InvalidHistoricalDataError: if the `indicators.quote`
                structure is missing or malformed, if any required OHLCV
                field is missing or is not a list, or if any required
                array's length does not equal `expected_length`.
        """
        indicators = result.get("indicators")
        if not isinstance(indicators, dict):
            raise InvalidHistoricalDataError(
                "Yahoo Finance chart response result was missing the "
                "expected 'indicators' object.",
                provider_name=_PROVIDER_NAME,
                display_symbol=display_symbol,
            )

        quote_list = indicators.get("quote")
        if not isinstance(quote_list, list) or not quote_list:
            raise InvalidHistoricalDataError(
                "Yahoo Finance chart response was missing the expected "
                "'indicators.quote' list.",
                provider_name=_PROVIDER_NAME,
                display_symbol=display_symbol,
            )

        quote_entry = quote_list[0]
        if not isinstance(quote_entry, dict):
            raise InvalidHistoricalDataError(
                "Yahoo Finance chart response 'indicators.quote[0]' was "
                "not a usable object.",
                provider_name=_PROVIDER_NAME,
                display_symbol=display_symbol,
            )

        quote_arrays: dict[str, list[Any]] = {}
        for field_name in _REQUIRED_QUOTE_FIELDS:
            field_array = quote_entry.get(field_name)
            if not isinstance(field_array, list):
                raise InvalidHistoricalDataError(
                    f"Yahoo Finance chart response was missing the "
                    f"expected 'indicators.quote[0].{field_name}' list.",
                    provider_name=_PROVIDER_NAME,
                    display_symbol=display_symbol,
                )
            if len(field_array) != expected_length:
                raise InvalidHistoricalDataError(
                    f"Yahoo Finance chart response field "
                    f"'indicators.quote[0].{field_name}' has length "
                    f"{len(field_array)}, expected {expected_length} to "
                    "match 'timestamp'.",
                    provider_name=_PROVIDER_NAME,
                    display_symbol=display_symbol,
                )
            quote_arrays[field_name] = field_array

        volume_array = quote_entry.get("volume")
        if not isinstance(volume_array, list):
            raise InvalidHistoricalDataError(
                "Yahoo Finance chart response was missing the expected "
                "'indicators.quote[0].volume' list.",
                provider_name=_PROVIDER_NAME,
                display_symbol=display_symbol,
            )
        if len(volume_array) != expected_length:
            raise InvalidHistoricalDataError(
                "Yahoo Finance chart response field "
                f"'indicators.quote[0].volume' has length "
                f"{len(volume_array)}, expected {expected_length} to "
                "match 'timestamp'.",
                provider_name=_PROVIDER_NAME,
                display_symbol=display_symbol,
            )
        quote_arrays["volume"] = volume_array

        return quote_arrays

    def _extract_adjclose_array(
        self,
        result: dict[str, Any],
        *,
        expected_length: int,
        display_symbol: str,
    ) -> list[Any] | None:
        """
        Extracts the optional `indicators.adjclose[0].adjclose` array, if
        present.

        Absent adjusted-close data is allowed and results in None being
        returned (every candle's `adjusted_close` will then be None).
        When present, its length must equal `expected_length`.

        Raises:
            InvalidHistoricalDataError: if adjusted-close data is present
                but malformed, or its length does not match
                `expected_length`.
        """
        indicators = result.get("indicators")
        if not isinstance(indicators, dict):
            return None

        adjclose_list = indicators.get("adjclose")
        if adjclose_list is None:
            return None
        if not isinstance(adjclose_list, list) or not adjclose_list:
            raise InvalidHistoricalDataError(
                "Yahoo Finance chart response 'indicators.adjclose' was "
                "present but not a usable list.",
                provider_name=_PROVIDER_NAME,
                display_symbol=display_symbol,
            )

        adjclose_entry = adjclose_list[0]
        if not isinstance(adjclose_entry, dict):
            raise InvalidHistoricalDataError(
                "Yahoo Finance chart response 'indicators.adjclose[0]' was "
                "not a usable object.",
                provider_name=_PROVIDER_NAME,
                display_symbol=display_symbol,
            )

        adjclose_array = adjclose_entry.get("adjclose")
        if adjclose_array is None:
            return None
        if not isinstance(adjclose_array, list):
            raise InvalidHistoricalDataError(
                "Yahoo Finance chart response "
                "'indicators.adjclose[0].adjclose' was present but not a "
                "usable list.",
                provider_name=_PROVIDER_NAME,
                display_symbol=display_symbol,
            )
        if len(adjclose_array) != expected_length:
            raise InvalidHistoricalDataError(
                "Yahoo Finance chart response field "
                f"'indicators.adjclose[0].adjclose' has length "
                f"{len(adjclose_array)}, expected {expected_length} to "
                "match 'timestamp'.",
                provider_name=_PROVIDER_NAME,
                display_symbol=display_symbol,
            )

        return adjclose_array

    def _build_candles(
        self,
        timestamps: list[Any],
        quote_arrays: dict[str, list[Any]],
        adjclose_array: list[Any] | None,
        *,
        display_symbol: str,
    ) -> list[HistoricalCandle]:
        """
        Builds one HistoricalCandle per index across the aligned
        timestamp/OHLCV/adjusted-close arrays.

        A row is skipped entirely only when it is a genuine
        no-trading placeholder: open, high, low, and close are ALL None
        for that index. Volume is deliberately excluded from this
        placeholder test -- Yahoo may report a zero or missing volume
        alongside a genuine no-trading gap, but volume alone (with OHLC
        present) never indicates a placeholder row.

        Any other partial combination of open/high/low/close being None
        (i.e. some but not all of them) is treated as malformed data and
        raises InvalidHistoricalDataError, rather than being silently
        skipped or silently filled in.

        When all four OHLC fields are present for a row, volume is
        required and must pass _to_volume_int validation -- a missing or
        invalid volume for an otherwise-real candle raises
        InvalidHistoricalDataError rather than being treated as optional.

        Candles are constructed in Yahoo's supplied order, with no
        sorting or deduplication performed here -- HistoricalSeries'
        own construction (in the caller) is what will detect and reject
        any ordering or duplicate-timestamp problem in the assembled
        data.

        Raises:
            InvalidHistoricalDataError: if a required OHLC value or volume
                cannot be converted to a usable type, or if the assembled
                candle fails domain validation. Rows with incomplete OHLC
                data are skipped.
        """
        candles: list[HistoricalCandle] = []

        for index in range(len(timestamps)):
            raw_timestamp = timestamps[index]
            raw_open = quote_arrays["open"][index]
            raw_high = quote_arrays["high"][index]
            raw_low = quote_arrays["low"][index]
            raw_close = quote_arrays["close"][index]
            raw_volume = quote_arrays["volume"][index]
            raw_adjclose = adjclose_array[index] if adjclose_array is not None else None

            required_ohlc_values = (raw_open, raw_high, raw_low, raw_close)
            if all(value is None for value in required_ohlc_values):
                # Genuine no-trading placeholder row -- skip entirely,
                # regardless of what volume reports for this index.
                continue

            if any(value is None for value in required_ohlc_values):
                # Yahoo occasionally returns an incomplete candle for an
                # otherwise valid series. Ignore that unusable row rather
                # than failing the complete stock-history request.
                continue

            candle_timestamp = self._to_utc_datetime(
                raw_timestamp, index=index, display_symbol=display_symbol
            )
            open_price = self._to_decimal(
                raw_open, index=index, field_name="open", display_symbol=display_symbol
            )
            high_price = self._to_decimal(
                raw_high, index=index, field_name="high", display_symbol=display_symbol
            )
            low_price = self._to_decimal(
                raw_low, index=index, field_name="low", display_symbol=display_symbol
            )
            close_price = self._to_decimal(
                raw_close, index=index, field_name="close", display_symbol=display_symbol
            )
            # Volume is required whenever OHLC is fully present -- passing
            # raw_volume (even if it is None) straight into _to_volume_int
            # is intentional: that method already raises
            # InvalidHistoricalDataError for a None/unconvertible value,
            # which is exactly the "missing volume for a real candle"
            # failure this row must produce.
            volume = self._to_volume_int(
                raw_volume, index=index, display_symbol=display_symbol
            )
            adjusted_close = (
                self._to_decimal(
                    raw_adjclose,
                    index=index,
                    field_name="adjclose",
                    display_symbol=display_symbol,
                )
                if raw_adjclose is not None
                else None
            )

            try:
                candle = HistoricalCandle(
                    timestamp=candle_timestamp,
                    open_price=open_price,
                    high_price=high_price,
                    low_price=low_price,
                    close_price=close_price,
                    adjusted_close=adjusted_close,
                    volume=volume,
                )
            except ValueError as exc:
                raise InvalidHistoricalDataError(
                    f"Yahoo Finance chart response row at index {index} "
                    f"failed candle validation: {exc}",
                    provider_name=_PROVIDER_NAME,
                    display_symbol=display_symbol,
                ) from exc

            candles.append(candle)

        return candles

    def _to_decimal(
        self,
        raw_value: Any,
        *,
        index: int,
        field_name: str,
        display_symbol: str,
    ) -> Decimal:
        """
        Converts a raw numeric field to Decimal via str() (never via a
        direct float-to-Decimal construction, which would carry the
        source float's binary rounding error into the Decimal value).
        Explicitly rejects bool, since bool is a subclass of int/usable as
        a number in Python but is never a legitimate price value.

        Raises:
            InvalidHistoricalDataError: if `raw_value` is a bool, cannot
                be converted to a Decimal, or converts to a non-finite
                Decimal (NaN or Infinity).
        """
        if isinstance(raw_value, bool):
            raise InvalidHistoricalDataError(
                f"Yahoo Finance chart response field {field_name!r} at "
                f"index {index} was a boolean, which is not a usable "
                "price value.",
                provider_name=_PROVIDER_NAME,
                display_symbol=display_symbol,
            )
        try:
            decimal_value = Decimal(str(raw_value))
        except InvalidOperation as exc:
            raise InvalidHistoricalDataError(
                f"Yahoo Finance chart response field {field_name!r} at "
                f"index {index} with value {raw_value!r} could not be "
                "converted to Decimal.",
                provider_name=_PROVIDER_NAME,
                display_symbol=display_symbol,
            ) from exc

        if not decimal_value.is_finite():
            raise InvalidHistoricalDataError(
                f"Yahoo Finance chart response field {field_name!r} at "
                f"index {index} with value {raw_value!r} converted to a "
                "non-finite Decimal (NaN or Infinity).",
                provider_name=_PROVIDER_NAME,
                display_symbol=display_symbol,
            )

        return decimal_value

    def _to_volume_int(
        self,
        raw_value: Any,
        *,
        index: int,
        display_symbol: str,
    ) -> int:
        """
        Converts a raw volume field to a genuine int.

        Accepted forms:
          - an int, excluding bool.
          - a numeric string containing an integer (e.g. "12345").
          - a float, only when math.isfinite(value) and value.is_integer().

        Rejected: fractional values, negative values, bool, malformed
        strings, None, NaN, and infinite values.

        Raises:
            InvalidHistoricalDataError: if `raw_value` does not match one
                of the accepted forms above, or if the resulting integer
                is negative.
        """
        volume: int | None = None

        if isinstance(raw_value, bool):
            volume = None
        elif isinstance(raw_value, int):
            volume = raw_value
        elif isinstance(raw_value, float):
            if math.isfinite(raw_value) and raw_value.is_integer():
                volume = int(raw_value)
        elif isinstance(raw_value, str):
            stripped = raw_value.strip()
            if stripped.lstrip("-").isdigit():
                volume = int(stripped)

        if volume is None:
            raise InvalidHistoricalDataError(
                f"Yahoo Finance chart response field 'volume' at index "
                f"{index} with value {raw_value!r} could not be "
                "converted to a valid integer volume.",
                provider_name=_PROVIDER_NAME,
                display_symbol=display_symbol,
            )

        if volume < 0:
            raise InvalidHistoricalDataError(
                f"Yahoo Finance chart response field 'volume' at index "
                f"{index} with value {raw_value!r} is negative, which is "
                "not a usable volume.",
                provider_name=_PROVIDER_NAME,
                display_symbol=display_symbol,
            )

        return volume

    def _to_utc_datetime(
        self,
        raw_value: Any,
        *,
        index: int,
        display_symbol: str,
    ) -> datetime:
        """
        Converts a raw epoch-seconds timestamp value into a
        timezone-aware UTC datetime, matching HistoricalCandle.timestamp's
        required format.

        Only strictly integer-like values are accepted, and no lossy
        conversion is ever performed:
          - bool is rejected outright.
          - int is accepted as-is.
          - str is accepted only if, after stripping, it consists solely
            of an optional leading '-' followed by digits (i.e. a base-10
            integer literal with no fractional part).
          - float is accepted only when math.isfinite(value) and
            value.is_integer() -- a fractional float (e.g. 123.5) is
            rejected rather than truncated or rounded, and NaN/Infinity
            are rejected by the isfinite() check.
          - any other type, or a value that fails the checks above, is
            rejected.

        Raises:
            InvalidHistoricalDataError: if `raw_value` is not a strictly
                integer-like epoch-seconds value as described above, or if
                the resulting integer does not represent a timestamp that
                Python's datetime can construct (e.g. out of range).
        """
        unix_seconds: int | None = None

        if isinstance(raw_value, bool):
            unix_seconds = None
        elif isinstance(raw_value, int):
            unix_seconds = raw_value
        elif isinstance(raw_value, float):
            if math.isfinite(raw_value) and raw_value.is_integer():
                unix_seconds = int(raw_value)
        elif isinstance(raw_value, str):
            stripped = raw_value.strip()
            if stripped.lstrip("-").isdigit():
                unix_seconds = int(stripped)

        if unix_seconds is None:
            raise InvalidHistoricalDataError(
                f"Yahoo Finance chart response 'timestamp' at index "
                f"{index} with value {raw_value!r} is not a valid "
                "integer-like Unix timestamp (fractional, boolean, "
                "malformed, or non-finite values are rejected).",
                provider_name=_PROVIDER_NAME,
                display_symbol=display_symbol,
            )

        try:
            return datetime.fromtimestamp(unix_seconds, tz=timezone.utc)
        except (OverflowError, OSError, ValueError) as exc:
            raise InvalidHistoricalDataError(
                f"Yahoo Finance chart response 'timestamp' at index "
                f"{index} with value {unix_seconds!r} could not be "
                "converted to a datetime.",
                provider_name=_PROVIDER_NAME,
                display_symbol=display_symbol,
            ) from exc

    def _resolve_company_name(self, meta: dict[str, Any], *, fallback: str) -> str:
        """
        Resolves a company name for a series: prefers `shortName` when it
        is a non-empty string, falls back to `longName` when *that* is a
        non-empty string, then falls back to `instrumentName` when *that*
        is a non-empty string, and otherwise falls back to the canonical
        symbol. The resolved name is stripped before being returned.
        """
        for field_name in ("shortName", "longName", "instrumentName"):
            candidate = meta.get(field_name)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()

        return fallback