# backend/app/modules/stock_details/infrastructure/providers/yahoo_quote_provider.py
"""
Yahoo Finance implementation of StockQuoteProviderPort.

This infrastructure adapter is the only part of the stock_details module
that knows Yahoo Finance's endpoint, symbols, response fields, or HTTP
behavior. It translates Yahoo-specific data and failures into the
stock_details module's domain entities and exceptions.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Final, NoReturn

import httpx

from app.modules.stock_details.application.ports import StockQuoteProviderPort
from app.modules.stock_details.domain.entities import StockQuote
from app.modules.stock_details.domain.exceptions import (
    InvalidQuoteDataError,
    QuoteProviderRateLimitedError,
    QuoteProviderTimeoutError,
    QuoteProviderUnavailableError,
)
from app.modules.stock_search.domain.entities import StockExchange


_CHART_ENDPOINT_URL_TEMPLATE: Final[str] = (
    "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
)

_CHART_QUERY_PARAMS: Final[dict[str, str]] = {
    "interval": "1d",
    "range": "5d",
}

_REQUEST_HEADERS: Final[dict[str, str]] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

_EXCHANGE_TOKEN_TO_YAHOO_SUFFIX: Final[dict[str, str]] = {
    "NSE": ".NS",
    "BSE": ".BO",
}

_PROVIDER_NAME: Final[str] = "YahooQuoteProvider"


class YahooQuoteProvider(StockQuoteProviderPort):
    """
    Fetches current stock quotes from Yahoo Finance's chart endpoint.

    A shared httpx.AsyncClient is injected and owned by the module's
    dependency lifespan. This provider must never close that client.
    """

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        request_timeout_seconds: float,
    ) -> None:
        self._http_client = http_client
        self._request_timeout_seconds = request_timeout_seconds

    async def get_quote(self, display_symbol: str) -> StockQuote:
        """
        Fetches and converts one Yahoo Finance quote into StockQuote.

        Args:
            display_symbol: Validated symbol in the form SYMBOL.EXCHANGE,
                such as RELIANCE.NSE or 500325.BSE.

        Returns:
            A validated StockQuote domain entity.

        Raises:
            QuoteProviderTimeoutError: Yahoo did not respond in time.
            QuoteProviderRateLimitedError: Yahoo returned HTTP 429.
            QuoteProviderUnavailableError: Yahoo was unreachable, denied
                access, or returned a server error.
            InvalidQuoteDataError: Yahoo returned missing, malformed, or
                unusable quote data.
        """
        canonical_symbol, exchange_token = self._split_display_symbol(
            display_symbol
        )
        yahoo_symbol = self._to_yahoo_symbol(
            canonical_symbol,
            exchange_token,
        )

        response = await self._fetch_chart_response(
            yahoo_symbol=yahoo_symbol,
            display_symbol=display_symbol,
        )

        return self._parse_chart_response(
            response=response,
            display_symbol=display_symbol,
            canonical_symbol=canonical_symbol,
            exchange_token=exchange_token,
        )

    @staticmethod
    def _split_display_symbol(
        display_symbol: str,
    ) -> tuple[str, str]:
        """
        Splits a previously validated SYMBOL.EXCHANGE display symbol.
        """
        canonical_symbol, _, exchange_token = display_symbol.rpartition(
            "."
        )
        return canonical_symbol, exchange_token

    @staticmethod
    def _to_yahoo_symbol(
        canonical_symbol: str,
        exchange_token: str,
    ) -> str:
        """
        Converts AlphaEdge symbols into Yahoo symbols.

        Examples:
            RELIANCE.NSE -> RELIANCE.NS
            500325.BSE   -> 500325.BO
        """
        yahoo_suffix = _EXCHANGE_TOKEN_TO_YAHOO_SUFFIX[exchange_token]
        return f"{canonical_symbol}{yahoo_suffix}"

    async def _fetch_chart_response(
        self,
        *,
        yahoo_symbol: str,
        display_symbol: str,
    ) -> httpx.Response:
        """
        Calls Yahoo's chart endpoint and translates HTTP failures.
        """
        url = _CHART_ENDPOINT_URL_TEMPLATE.format(
            symbol=yahoo_symbol
        )

        try:
            response = await self._http_client.get(
                url,
                params=_CHART_QUERY_PARAMS,
                headers=_REQUEST_HEADERS,
                timeout=httpx.Timeout(
                    self._request_timeout_seconds
                ),
            )
        except httpx.TimeoutException as exc:
            raise QuoteProviderTimeoutError(
                (
                    "Yahoo Finance request timed out after "
                    f"{self._request_timeout_seconds} second(s)."
                ),
                provider_name=_PROVIDER_NAME,
            ) from exc
        except httpx.HTTPError as exc:
            raise QuoteProviderUnavailableError(
                "Yahoo Finance request failed at the transport level.",
                provider_name=_PROVIDER_NAME,
            ) from exc

        if response.status_code == 429:
            raise QuoteProviderRateLimitedError(
                "Yahoo Finance is rate-limiting quote requests.",
                provider_name=_PROVIDER_NAME,
                retry_after_seconds=self._parse_retry_after(
                    response
                ),
            )

        if response.status_code in {401, 403}:
            raise QuoteProviderUnavailableError(
                (
                    "Yahoo Finance denied access with HTTP "
                    f"{response.status_code}."
                ),
                provider_name=_PROVIDER_NAME,
            )

        if response.status_code >= 500:
            raise QuoteProviderUnavailableError(
                (
                    "Yahoo Finance returned server error HTTP "
                    f"{response.status_code}."
                ),
                provider_name=_PROVIDER_NAME,
            )

        if response.status_code >= 400:
            raise InvalidQuoteDataError(
                (
                    "Yahoo Finance returned unexpected client error "
                    f"HTTP {response.status_code}."
                ),
                provider_name=_PROVIDER_NAME,
                display_symbol=display_symbol,
            )

        return response

    @staticmethod
    def _parse_retry_after(
        response: httpx.Response,
    ) -> int | None:
        """
        Returns a valid non-negative Retry-After value when available.
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
        *,
        response: httpx.Response,
        display_symbol: str,
        canonical_symbol: str,
        exchange_token: str,
    ) -> StockQuote:
        """
        Converts Yahoo's chart response into a StockQuote.

        Current price and previous close are primarily read from `meta`.
        Daily OHLC values are read from `indicators.quote[0]`, because
        Yahoo does not reliably include regularMarketOpen,
        regularMarketDayHigh, or regularMarketDayLow in `meta`.
        """
        body = self._parse_json_body(
            response=response,
            display_symbol=display_symbol,
        )

        chart = body.get("chart")
        if not isinstance(chart, dict):
            self._raise_invalid_data(
                display_symbol,
                "Yahoo response was missing the 'chart' object.",
            )

        chart_error = chart.get("error")
        if chart_error:
            self._raise_invalid_data(
                display_symbol,
                (
                    "Yahoo returned a chart-level error for the "
                    "requested symbol."
                ),
            )

        result_list = chart.get("result")
        if not isinstance(result_list, list) or not result_list:
            self._raise_invalid_data(
                display_symbol,
                "Yahoo response did not contain a quote result.",
            )

        result = result_list[0]
        if not isinstance(result, dict):
            self._raise_invalid_data(
                display_symbol,
                "Yahoo quote result was not a valid object.",
            )

        meta = result.get("meta")
        if not isinstance(meta, dict):
            self._raise_invalid_data(
                display_symbol,
                "Yahoo quote result was missing its metadata.",
            )

        quote_data = self._extract_quote_data(
            result=result,
            display_symbol=display_symbol,
        )

        price_raw = meta.get("regularMarketPrice")
        if price_raw is None:
            price_raw = self._last_non_none(
                quote_data.get("close")
            )

        price = self._to_decimal(
            price_raw,
            display_symbol=display_symbol,
            field_name="regularMarketPrice/close",
        )

        # open/high/low must all come from the SAME source -- either all
        # three from meta's live day-range fields, or all three from the
        # same daily-candle index -- never mixed. Mixing sources could
        # otherwise combine, e.g., today's live open/low from meta with
        # yesterday's completed-candle high, producing a day range that
        # never actually occurred in any single session.
        open_raw, high_raw, low_raw = self._resolve_atomic_day_range(
            meta=meta,
            quote_data=quote_data,
        )

        open_price = self._to_decimal(
            open_raw,
            display_symbol=display_symbol,
            field_name="regularMarketOpen/open (atomic day-range source)",
        )

        high_price = self._to_decimal(
            high_raw,
            display_symbol=display_symbol,
            field_name="regularMarketDayHigh/high (atomic day-range source)",
        )

        low_price = self._to_decimal(
            low_raw,
            display_symbol=display_symbol,
            field_name="regularMarketDayLow/low (atomic day-range source)",
        )

        previous_close_raw = meta.get("chartPreviousClose")
        if previous_close_raw is None:
            previous_close_raw = meta.get("previousClose")

        previous_close = self._to_decimal(
            previous_close_raw,
            display_symbol=display_symbol,
            field_name="chartPreviousClose/previousClose",
        )

        if previous_close == Decimal("0"):
            self._raise_invalid_data(
                display_symbol,
                "Yahoo returned a zero previous close.",
            )

        change = price - previous_close
        change_percent = (
            change / previous_close
        ) * Decimal("100")

        timestamp_raw = meta.get("regularMarketTime")
        if timestamp_raw is None:
            timestamp_raw = self._last_non_none(
                result.get("timestamp")
            )

        as_of = self._to_utc_datetime(
            timestamp_raw,
            display_symbol=display_symbol,
        )

        company_name = self._resolve_company_name(
            meta=meta,
            fallback=canonical_symbol,
        )

        try:
            exchange = StockExchange(exchange_token)
        except ValueError as exc:
            raise InvalidQuoteDataError(
                (
                    "The validated exchange token could not be mapped "
                    "to StockExchange."
                ),
                provider_name=_PROVIDER_NAME,
                display_symbol=display_symbol,
            ) from exc

        try:
            return StockQuote(
                symbol=canonical_symbol,
                display_symbol=display_symbol,
                company_name=company_name,
                exchange=exchange,
                price=price,
                change=change,
                change_percent=change_percent,
                open_price=open_price,
                high_price=high_price,
                low_price=low_price,
                previous_close=previous_close,
                as_of=as_of,
            )
        except ValueError as exc:
            raise InvalidQuoteDataError(
                (
                    "Yahoo Finance returned values that failed "
                    f"StockQuote validation: {exc}"
                ),
                provider_name=_PROVIDER_NAME,
                display_symbol=display_symbol,
            ) from exc

    def _parse_json_body(
        self,
        *,
        response: httpx.Response,
        display_symbol: str,
    ) -> dict[str, Any]:
        """
        Parses and validates the top-level Yahoo JSON response.
        """
        try:
            body = response.json()
        except ValueError as exc:
            raise InvalidQuoteDataError(
                "Yahoo Finance returned invalid JSON.",
                provider_name=_PROVIDER_NAME,
                display_symbol=display_symbol,
            ) from exc

        if not isinstance(body, dict):
            self._raise_invalid_data(
                display_symbol,
                "Yahoo Finance response was not a JSON object.",
            )

        return body

    def _extract_quote_data(
        self,
        *,
        result: dict[str, Any],
        display_symbol: str,
    ) -> dict[str, Any]:
        """
        Extracts `indicators.quote[0]` from Yahoo's chart response.
        """
        indicators = result.get("indicators")
        if not isinstance(indicators, dict):
            self._raise_invalid_data(
                display_symbol,
                "Yahoo response was missing quote indicators.",
            )

        quote_list = indicators.get("quote")
        if not isinstance(quote_list, list) or not quote_list:
            self._raise_invalid_data(
                display_symbol,
                "Yahoo response did not contain daily quote values.",
            )

        quote_data = quote_list[0]
        if not isinstance(quote_data, dict):
            self._raise_invalid_data(
                display_symbol,
                "Yahoo daily quote data was malformed.",
            )

        return quote_data

    def _resolve_atomic_day_range(
        self,
        *,
        meta: dict[str, Any],
        quote_data: dict[str, Any],
    ) -> tuple[Any, Any, Any]:
        """
        Selects open/high/low from a single, consistent source, never
        combining a value from `meta` with a value from the daily candle
        arrays for the other fields.

        Returns `meta`'s (regularMarketOpen, regularMarketDayHigh,
        regularMarketDayLow) only when all three are present (not None).
        If any one of the three is missing from `meta`, none of the three
        meta values are used -- instead all three are taken together from
        `quote_data` via `_latest_atomic_candle_ohl`, so the eventual
        result always describes a single, real session rather than a
        combination of a live tick and a stale completed candle.
        """
        meta_open = meta.get("regularMarketOpen")
        meta_high = meta.get("regularMarketDayHigh")
        meta_low = meta.get("regularMarketDayLow")

        if meta_open is not None and meta_high is not None and meta_low is not None:
            return meta_open, meta_high, meta_low

        return self._latest_atomic_candle_ohl(quote_data)

    @staticmethod
    def _latest_atomic_candle_ohl(quote_data: dict[str, Any]) -> tuple[Any, Any, Any]:
        """
        Returns the open/high/low values from the single latest daily
        candle index at which all three of `quote_data`'s "open",
        "high", and "low" arrays have a non-None value simultaneously.

        This never returns open/high/low from three different indices
        (each array can have its own, independent null pattern) --
        every returned triple comes from exactly one index, i.e. exactly
        one trading day's candle. Returns (None, None, None) if the
        arrays are missing/malformed, or if no single index has all three
        values present; the caller's existing _to_decimal handling
        already raises InvalidQuoteDataError for a None value, so that
        failure path is unchanged.
        """
        open_array = quote_data.get("open")
        high_array = quote_data.get("high")
        low_array = quote_data.get("low")

        if not (
            isinstance(open_array, list)
            and isinstance(high_array, list)
            and isinstance(low_array, list)
        ):
            return None, None, None

        common_length = min(len(open_array), len(high_array), len(low_array))
        for index in range(common_length - 1, -1, -1):
            candidate_open = open_array[index]
            candidate_high = high_array[index]
            candidate_low = low_array[index]
            if (
                candidate_open is not None
                and candidate_high is not None
                and candidate_low is not None
            ):
                return candidate_open, candidate_high, candidate_low

        return None, None, None

    @staticmethod
    def _last_non_none(raw_value: Any) -> Any:
        """
        Returns the final non-None value from a list.

        Returns non-list values unchanged. This lets the parser tolerate
        Yahoo responses where historical arrays contain null entries.
        """
        if not isinstance(raw_value, list):
            return raw_value

        for value in reversed(raw_value):
            if value is not None:
                return value

        return None

    @staticmethod
    def _resolve_company_name(
        *,
        meta: dict[str, Any],
        fallback: str,
    ) -> str:
        """
        Resolves the best available company display name.
        """
        for field_name in (
            "shortName",
            "longName",
            "instrumentName",
        ):
            value = meta.get(field_name)
            if isinstance(value, str) and value.strip():
                return value.strip()

        return fallback

    def _to_decimal(
        self,
        raw_value: Any,
        *,
        display_symbol: str,
        field_name: str,
    ) -> Decimal:
        """
        Converts a Yahoo numeric value using Decimal(str(value)).
        """
        if raw_value is None:
            self._raise_invalid_data(
                display_symbol,
                f"Required numeric field {field_name!r} was missing.",
            )

        if isinstance(raw_value, bool):
            self._raise_invalid_data(
                display_symbol,
                f"Field {field_name!r} contained a Boolean value.",
            )

        try:
            decimal_value = Decimal(str(raw_value))
        except (InvalidOperation, ValueError) as exc:
            raise InvalidQuoteDataError(
                (
                    f"Field {field_name!r} could not be converted "
                    "to Decimal."
                ),
                provider_name=_PROVIDER_NAME,
                display_symbol=display_symbol,
            ) from exc

        if not decimal_value.is_finite():
            self._raise_invalid_data(
                display_symbol,
                f"Field {field_name!r} was not finite.",
            )

        return decimal_value

    def _to_utc_datetime(
        self,
        raw_value: Any,
        *,
        display_symbol: str,
    ) -> datetime:
        """
        Converts Unix epoch seconds to a timezone-aware UTC datetime.
        """
        if raw_value is None:
            self._raise_invalid_data(
                display_symbol,
                "Yahoo response was missing the quote timestamp.",
            )

        if isinstance(raw_value, bool):
            self._raise_invalid_data(
                display_symbol,
                "Yahoo quote timestamp contained a Boolean value.",
            )

        try:
            unix_seconds = int(raw_value)
        except (TypeError, ValueError) as exc:
            raise InvalidQuoteDataError(
                "Yahoo quote timestamp was invalid.",
                provider_name=_PROVIDER_NAME,
                display_symbol=display_symbol,
            ) from exc

        try:
            return datetime.fromtimestamp(
                unix_seconds,
                tz=timezone.utc,
            )
        except (OverflowError, OSError, ValueError) as exc:
            raise InvalidQuoteDataError(
                "Yahoo quote timestamp was outside the supported range.",
                provider_name=_PROVIDER_NAME,
                display_symbol=display_symbol,
            ) from exc

    @staticmethod
    def _raise_invalid_data(
        display_symbol: str,
        message: str,
    ) -> NoReturn:
        """
        Raises a consistently constructed InvalidQuoteDataError.

        Typed as NoReturn (rather than None) so static type checkers can
        verify that code following a call to this method is genuinely
        unreachable, e.g. after `if not isinstance(x, dict):
        self._raise_invalid_data(...)`, the checker can confirm `x` is a
        dict in every subsequent line without a redundant narrowing.
        """
        raise InvalidQuoteDataError(
            message,
            provider_name=_PROVIDER_NAME,
            display_symbol=display_symbol,
        )