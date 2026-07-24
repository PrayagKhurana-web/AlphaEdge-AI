"""
Domain entities for the stock_history module.

These are pure Python objects with zero framework dependencies (no
FastAPI, no Pydantic, no httpx, no infrastructure-layer concern, no
configuration). They represent the concept of a historical OHLCV candle
series independent of where the data came from or how it's transported.
Per PROJECT_CONTEXT.md's Clean Architecture rule, this file must never
import from application/, infrastructure/, or api/.

This module deliberately reuses StockExchange from
app.modules.stock_search.domain.entities rather than defining a duplicate
exchange enum, for the same reason stock_details does: both modules'
domain layers share this single, provider-agnostic concept of which
Indian exchange a symbol belongs to. This is an intentional,
explicit domain-to-domain coupling (distinct from reaching into another
module's private infrastructure/application state, which
PROJECT_CONTEXT.md prohibits).

These entities are the clean data foundation that future technical
indicators, backtesting, feature engineering, and prediction models will
be built on top of. Because of that downstream role, this file enforces
strict validation and deterministic ordering now, rather than leaving
"is this data actually usable" as a question every future consumer has to
re-answer for itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from app.modules.stock_search.domain.entities import StockExchange


def _require_non_empty(value: str, field_name: str) -> None:
    """
    Raises ValueError if `value` is empty or consists only of whitespace.

    Centralizing this check keeps the validation rule identical across
    every string field below, consistent with the equivalent helpers in
    stock_search.domain.entities and stock_details.domain.entities.
    """
    if not value or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string, got {value!r}")


def _require_utc_datetime(value: datetime, field_name: str) -> None:
    """
    Raises ValueError unless `value` is a timezone-aware datetime whose
    UTC offset is exactly zero.

    Mirrors market_data.domain.entities._require_utc_datetime and
    stock_details.domain.entities._require_utc_datetime exactly: this
    rejects naive datetimes (no tzinfo at all) as well as timezone-aware
    datetimes that aren't UTC (e.g. IST, +05:30). UTC is used
    consistently across every timestamp in this codebase (matching
    DATABASE.md's TIMESTAMPTZ convention) precisely so that candles from
    different providers, or candles combined with indicator/prediction
    timestamps from other modules, can be compared and ordered without
    every consumer having to reason about time zone conversion first.
    """
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(
            f"{field_name} must be a timezone-aware datetime, got a naive "
            f"datetime: {value!r}"
        )
    if value.utcoffset() != timedelta(0):
        raise ValueError(
            f"{field_name} must be in UTC (zero offset), got an offset of "
            f"{value.utcoffset()!r} for value: {value!r}"
        )


def _require_finite_decimal(value: Decimal, field_name: str) -> None:
    """
    Raises ValueError if `value` is not actually a Decimal, or is a
    Decimal that is not finite (i.e. is NaN or Infinity).

    Decimal is used for every price field in this codebase (never float)
    because float's binary representation cannot exactly represent most
    decimal fractions, and repeated arithmetic on floats (as indicators,
    backtests, and ML feature pipelines will all eventually do to this
    data) compounds that imprecision. The type check happens first and is
    strict: int, float, str, or any other type is rejected outright with
    a clear error identifying the offending type, rather than being
    silently coerced into Decimal. Callers must supply a genuine Decimal
    (e.g. constructed via Decimal(str(raw_value)) upstream, in the
    infrastructure layer) -- never a float or other numeric type for this
    entity to coerce.
    """
    if not isinstance(value, Decimal):
        raise ValueError(
            f"{field_name} must be a Decimal instance, got "
            f"{type(value).__name__} with value {value!r}"
        )
    if not value.is_finite():
        raise ValueError(
            f"{field_name} must be a finite Decimal, got a non-finite "
            f"value (NaN or Infinity): {value!r}"
        )


def _require_non_negative_decimal(value: Decimal, field_name: str) -> None:
    """Raises ValueError if `value` is negative."""
    if value < Decimal("0"):
        raise ValueError(f"{field_name} must be non-negative, got {value!r}")


@dataclass(frozen=True, slots=True)
class HistoricalCandle:
    """
    A single OHLCV (open/high/low/close/volume) observation for one
    trading interval.

    Attributes:
        timestamp: UTC timestamp (timezone-aware, zero offset) identifying
            which interval this candle covers (e.g. the start of a
            1-minute or 1-day bar, per whatever interval convention the
            owning HistoricalSeries declares).
        open_price: Opening price for the interval. Must be a
            non-negative, finite Decimal.
        high_price: Highest traded price during the interval. Must be a
            non-negative, finite Decimal, and not below `low_price`.
        low_price: Lowest traded price during the interval. Must be a
            non-negative, finite Decimal.
        close_price: Closing price for the interval. Must be a
            non-negative, finite Decimal.
        adjusted_close: Closing price adjusted for corporate actions
            (splits, dividends), if the provider supplies one. None when
            no adjusted value is available or applicable (e.g. intraday
            intervals, or providers that don't compute adjustments) --
            its absence is a normal, expected state, not an error. When
            present, must be a non-negative, finite Decimal.
        volume: Number of shares/units traded during the interval. Must be
            a genuine int (not a bool -- Python's bool is a subclass of
            int, so `True`/`False` are explicitly rejected rather than
            silently accepted as 1/0) and non-negative.

    Design notes:
        - `open_price` and `close_price` are intentionally NOT required to
          fall within [`low_price`, `high_price`]. Upstream providers can
          return adjusted values or slightly asynchronous snapshots of
          these fields, so enforcing that relationship here would reject
          otherwise-legitimate provider data -- this mirrors
          stock_details.domain.entities.StockQuote's identical reasoning
          for `price` versus `high_price`/`low_price`.
        - No Decimal field is ever constructed from a float inside this
          entity, and none should be upstream of it either.

    Raises:
        ValueError: if `timestamp` is not a UTC (zero-offset), timezone-
            aware datetime; if `open_price`, `high_price`, `low_price`,
            `close_price`, or (when not None) `adjusted_close` is not a
            Decimal instance or is a non-finite Decimal; if any of those
            price fields is negative; if `high_price` is less than
            `low_price`; if `volume` is a bool or not an int; or if
            `volume` is negative.
    """

    timestamp: datetime
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    close_price: Decimal
    adjusted_close: Decimal | None
    volume: int

    def __post_init__(self) -> None:
        _require_utc_datetime(self.timestamp, "HistoricalCandle.timestamp")

        for value, field_name in (
            (self.open_price, "HistoricalCandle.open_price"),
            (self.high_price, "HistoricalCandle.high_price"),
            (self.low_price, "HistoricalCandle.low_price"),
            (self.close_price, "HistoricalCandle.close_price"),
        ):
            _require_finite_decimal(value, field_name)
            _require_non_negative_decimal(value, field_name)

        if self.adjusted_close is not None:
            _require_finite_decimal(self.adjusted_close, "HistoricalCandle.adjusted_close")
            _require_non_negative_decimal(
                self.adjusted_close, "HistoricalCandle.adjusted_close"
            )

        if self.high_price < self.low_price:
            raise ValueError(
                f"HistoricalCandle.high_price ({self.high_price!r}) must "
                f"not be below HistoricalCandle.low_price ({self.low_price!r})"
            )

        # bool is a subclass of int in Python, so an isinstance(x, int)
        # check alone would silently accept True/False as 1/0. Volume is
        # a count of traded units and must never be a boolean value, so
        # bool is checked and rejected explicitly, before the general int
        # check.
        if isinstance(self.volume, bool) or not isinstance(self.volume, int):
            raise ValueError(
                f"HistoricalCandle.volume must be an int (and not a bool), "
                f"got {type(self.volume).__name__} with value {self.volume!r}"
            )
        if self.volume < 0:
            raise ValueError(
                f"HistoricalCandle.volume must be non-negative, got {self.volume!r}"
            )

    def is_bullish(self) -> bool:
        """Returns True if this candle closed higher than it opened."""
        return self.close_price > self.open_price

    def is_bearish(self) -> bool:
        """Returns True if this candle closed lower than it opened."""
        return self.close_price < self.open_price


@dataclass(frozen=True, slots=True)
class HistoricalSeries:
    """
    An ordered, immutable series of historical candles for one stock over
    one interval/period combination.

    Attributes:
        symbol: The canonical trading symbol on `exchange` (e.g.
            "RELIANCE"), matching the same convention as
            stock_search.domain.entities.StockSearchResult.symbol and
            stock_details.domain.entities.StockQuote.symbol.
        display_symbol: A UI-facing presentation identifier (e.g.
            "RELIANCE.NSE"), kept deliberately separate from `symbol` for
            the same reason documented on StockSearchResult.display_symbol
            and StockQuote.display_symbol.
        company_name: The issuing company's display name.
        exchange: The exchange this series was fetched from. Must already
            be a StockExchange instance -- this entity does not coerce
            strings (e.g. "NSE") into StockExchange.
        interval: The candle interval this series was fetched at (e.g.
            "1d", "1h", "1m"). Stored as a plain string rather than an
            enum for now, since the set of supported intervals is
            expected to be provider-dependent and may grow; validated
            only for non-emptiness at the domain level.
        period: The overall lookback period this series covers (e.g.
            "1mo", "1y", "max"). Same string-typing rationale as
            `interval`.
        candles: An immutable, ordered sequence of HistoricalCandle
            entries, strictly ascending by `timestamp` with no duplicate
            timestamps. Stored as a tuple (not a list) because a tuple is
            inherently immutable -- this guarantees that neither the
            stored sequence nor a caller's original list (if one was
            passed in) can alter this entity's candle data after
            construction, without needing a defensive copy or a
            MappingProxyType-style wrapper. This entity deliberately does
            NOT sort or deduplicate `candles` itself: a provider that
            returns unordered or duplicate data has produced invalid
            data, and silently repairing it here would hide a real
            problem from the infrastructure layer that should be
            surfacing it as InvalidQuoteDataError-equivalent failure
            (that translation is an infrastructure-layer concern, not a
            domain-entity concern). An empty tuple (zero candles) is
            accepted at the domain level -- whether "no data" is itself
            an error is an application/provider policy decision, not a
            domain invariant.
        fetched_at: UTC timestamp (timezone-aware, zero offset) of when
            this series was fetched/assembled.

    Why this matters for downstream consumers: technical indicators,
    backtesting, and feature engineering pipelines will all eventually
    walk `candles` assuming strict, deterministic ascending order with no
    gaps in timestamp identity (no duplicates). Enforcing that invariant
    once, here, means every future consumer can rely on it rather than
    re-validating or re-sorting the series itself.

    Raises:
        ValueError: if `symbol`, `display_symbol`, `company_name`,
            `interval`, or `period` is empty or whitespace-only after
            stripping; if `exchange` is not an actual StockExchange
            instance; if `fetched_at` is not a UTC (zero-offset),
            timezone-aware datetime; if `candles` is not a tuple; if any
            element of `candles` is not a HistoricalCandle instance; if
            `candles` is not strictly ascending by `timestamp`; or if
            `candles` contains a duplicate timestamp.
    """

    symbol: str
    display_symbol: str
    company_name: str
    exchange: StockExchange
    interval: str
    period: str
    candles: tuple[HistoricalCandle, ...]
    fetched_at: datetime

    def __post_init__(self) -> None:
        # The dataclass is frozen, so normal attribute assignment is
        # disallowed even inside __post_init__. object.__setattr__
        # bypasses that restriction for these intentional, controlled
        # normalization writes.
        object.__setattr__(self, "symbol", self.symbol.strip())
        object.__setattr__(self, "display_symbol", self.display_symbol.strip())
        object.__setattr__(self, "company_name", self.company_name.strip())
        object.__setattr__(self, "interval", self.interval.strip())
        object.__setattr__(self, "period", self.period.strip())

        _require_non_empty(self.symbol, "HistoricalSeries.symbol")
        _require_non_empty(self.display_symbol, "HistoricalSeries.display_symbol")
        _require_non_empty(self.company_name, "HistoricalSeries.company_name")
        _require_non_empty(self.interval, "HistoricalSeries.interval")
        _require_non_empty(self.period, "HistoricalSeries.period")

        if not isinstance(self.exchange, StockExchange):
            raise ValueError(
                "HistoricalSeries.exchange must be a StockExchange "
                f"instance, got {type(self.exchange).__name__} with "
                f"value {self.exchange!r}"
            )

        _require_utc_datetime(self.fetched_at, "HistoricalSeries.fetched_at")

        self._validate_candles()

    def _validate_candles(self) -> None:
        """
        Validates that `candles` is a tuple of HistoricalCandle instances,
        strictly ordered by ascending timestamp with no duplicates.

        This method only validates -- it never sorts, deduplicates, or
        otherwise mutates `candles`. An empty tuple is valid at this
        layer; deciding whether "zero candles" should itself be treated
        as an error is left to the application/provider layer.

        Raises:
            ValueError: if `candles` is not a tuple; if any element is
                not a HistoricalCandle instance; if the sequence is not
                strictly ascending by timestamp; or if two candles share
                the same timestamp.
        """
        if not isinstance(self.candles, tuple):
            raise ValueError(
                "HistoricalSeries.candles must be a tuple, got "
                f"{type(self.candles).__name__}"
            )

        for index, candle in enumerate(self.candles):
            if not isinstance(candle, HistoricalCandle):
                raise ValueError(
                    f"HistoricalSeries.candles[{index}] must be a "
                    f"HistoricalCandle instance, got "
                    f"{type(candle).__name__} with value {candle!r}"
                )

        for index in range(1, len(self.candles)):
            previous_timestamp = self.candles[index - 1].timestamp
            current_timestamp = self.candles[index].timestamp
            if current_timestamp == previous_timestamp:
                raise ValueError(
                    "HistoricalSeries.candles contains a duplicate "
                    f"timestamp at index {index}: {current_timestamp!r}"
                )
            if current_timestamp < previous_timestamp:
                raise ValueError(
                    "HistoricalSeries.candles must be strictly ascending "
                    f"by timestamp; candle at index {index} "
                    f"({current_timestamp!r}) is not after candle at "
                    f"index {index - 1} ({previous_timestamp!r})"
                )

    def latest(self) -> HistoricalCandle | None:
        """
        Returns the most recent candle in this series (the last element,
        since `candles` is guaranteed strictly ascending by timestamp), or
        None if this series has zero candles.
        """
        if not self.candles:
            return None
        return self.candles[-1]

    def earliest(self) -> HistoricalCandle | None:
        """
        Returns the oldest candle in this series (the first element,
        since `candles` is guaranteed strictly ascending by timestamp), or
        None if this series has zero candles.
        """
        if not self.candles:
            return None
        return self.candles[0]

    def candle_count(self) -> int:
        """Returns the number of candles in this series."""
        return len(self.candles)