"""
Domain entities for the stock_details module.

These are pure Python objects with zero framework dependencies (no
FastAPI, no Pydantic, no HTTP client, no infrastructure-layer concern).
They represent the concept of a "stock quote" independent of where the
data came from or how it's transported. Per PROJECT_CONTEXT.md's Clean
Architecture rule, this file must never import from application/,
infrastructure/, or api/.

This module deliberately reuses StockExchange from
app.modules.stock_search.domain.entities rather than defining a duplicate
exchange enum -- both modules' domain layers share this single,
provider-agnostic concept of which Indian exchange a symbol belongs to.
This is an intentional, explicit domain-to-domain coupling between two
modules (distinct from reaching into another module's private
infrastructure/application state, which PROJECT_CONTEXT.md prohibits): if
stock_search and stock_details are ever split into separately deployable
services, StockExchange would need to move to a shared location first.
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
    every string field below, consistent with the equivalent helper in
    stock_search.domain.entities.
    """
    if not value or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string, got {value!r}")


def _require_utc_datetime(value: datetime, field_name: str) -> None:
    """
    Raises ValueError unless `value` is a timezone-aware datetime whose
    UTC offset is exactly zero.

    Mirrors market_data.domain.entities._require_utc_datetime exactly:
    this rejects naive datetimes (no tzinfo at all) as well as
    timezone-aware datetimes that aren't UTC (e.g. IST, +05:30), matching
    DATABASE.md's TIMESTAMPTZ convention of storing everything in UTC.
    Any tzinfo implementation is accepted as long as its computed offset
    for this value is zero.
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

    The type check happens first and is strict: int, float, str, or any
    other type is rejected outright with a clear error identifying the
    offending type, rather than being silently coerced into Decimal or
    allowed to reach value.is_finite() and raise an unrelated
    AttributeError. This enforces the "no silent Decimal coercion" rule
    at the domain boundary itself -- callers must supply a genuine
    Decimal (e.g. constructed via Decimal(str(raw_value)) upstream),
    never a float or other numeric type for this entity to coerce.
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
class StockQuote:
    """
    A single point-in-time quote for one stock, including the day's
    open/high/low/previous-close alongside the current price and change.

    Attributes:
        symbol: The canonical trading symbol on `exchange` (e.g.
            "RELIANCE"), matching the same convention as
            stock_search.domain.entities.StockSearchResult.symbol.
        display_symbol: A UI-facing presentation identifier (e.g.
            "RELIANCE.NSE"), kept deliberately separate from `symbol` for
            the same reason documented on StockSearchResult.display_symbol
            -- presentation conventions can evolve independently of the
            canonical internal identifier.
        company_name: The issuing company's display name.
        exchange: The exchange this quote was matched on. Must already be
            a StockExchange instance -- this entity does not coerce
            strings (e.g. "NSE") into StockExchange.
        price: Last traded price. Must be a non-negative, finite Decimal.
        change: Absolute change from the previous close. May be negative
            (a decline), zero, or positive -- not independently validated
            for sign, and not recalculated from `price`/`previous_close`
            by this entity (see class-level note below).
        change_percent: Percentage change from the previous close. Same
            sign/recalculation notes as `change`.
        open_price: The day's opening price. Must be a non-negative,
            finite Decimal.
        high_price: The day's highest traded price so far. Must be a
            non-negative, finite Decimal, and not below `low_price`.
        low_price: The day's lowest traded price so far. Must be a
            non-negative, finite Decimal.
        previous_close: The prior session's closing price. Must be a
            non-negative, finite Decimal.
        as_of: UTC timestamp (timezone-aware, zero offset) of when this
            quote was observed/fetched.

    Design notes:
        - `change` and `change_percent` are accepted as supplied and are
          never recomputed from `price` and `previous_close` inside this
          entity -- reconciling or deriving these values (if ever needed)
          is an application- or infrastructure-layer concern, not a
          domain invariant this entity enforces.
        - `price` is intentionally NOT required to fall within
          [`low_price`, `high_price`]. Upstream providers can return
          slightly asynchronous snapshots of these fields (e.g. `price`
          reflecting a post-market tick that hasn't yet been folded into
          `high_price`/`low_price`), so enforcing that relationship here
          would reject otherwise-legitimate provider data.
        - All string fields are normalized (stripped) before validation.
        - No Decimal field is ever constructed from a float inside this
          entity, and none should be upstream of it either -- callers
          must supply genuine Decimal values (e.g. via
          Decimal(str(raw_value))), never Decimal(some_float). A
          non-Decimal value for any financial field is rejected outright,
          not coerced.

    Raises:
        ValueError: if `symbol`, `display_symbol`, or `company_name` is
            empty or whitespace-only after stripping; if `as_of` is not a
            UTC (zero-offset), timezone-aware datetime; if `exchange` is
            not an actual StockExchange instance; if any financial field
            (`price`, `change`, `change_percent`, `open_price`,
            `high_price`, `low_price`, `previous_close`) is not a Decimal
            instance or is a non-finite Decimal (NaN or Infinity); if
            `price`, `open_price`, `high_price`, `low_price`, or
            `previous_close` is negative; or if `high_price` is less than
            `low_price`.
    """

    symbol: str
    display_symbol: str
    company_name: str
    exchange: StockExchange
    price: Decimal
    change: Decimal
    change_percent: Decimal
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    previous_close: Decimal
    as_of: datetime

    def __post_init__(self) -> None:
        # The dataclass is frozen, so normal attribute assignment is
        # disallowed even inside __post_init__. object.__setattr__
        # bypasses that restriction for these intentional, controlled
        # normalization writes: each string field is stripped of
        # leading/trailing whitespace before validation, so the stored
        # value -- not just the value checked -- is guaranteed
        # whitespace-normalized.
        object.__setattr__(self, "symbol", self.symbol.strip())
        object.__setattr__(self, "display_symbol", self.display_symbol.strip())
        object.__setattr__(self, "company_name", self.company_name.strip())

        _require_non_empty(self.symbol, "StockQuote.symbol")
        _require_non_empty(self.display_symbol, "StockQuote.display_symbol")
        _require_non_empty(self.company_name, "StockQuote.company_name")

        if not isinstance(self.exchange, StockExchange):
            raise ValueError(
                "StockQuote.exchange must be a StockExchange instance, "
                f"got {type(self.exchange).__name__} with value "
                f"{self.exchange!r}"
            )

        _require_utc_datetime(self.as_of, "StockQuote.as_of")

        for value, field_name in (
            (self.price, "StockQuote.price"),
            (self.change, "StockQuote.change"),
            (self.change_percent, "StockQuote.change_percent"),
            (self.open_price, "StockQuote.open_price"),
            (self.high_price, "StockQuote.high_price"),
            (self.low_price, "StockQuote.low_price"),
            (self.previous_close, "StockQuote.previous_close"),
        ):
            _require_finite_decimal(value, field_name)

        for value, field_name in (
            (self.price, "StockQuote.price"),
            (self.open_price, "StockQuote.open_price"),
            (self.high_price, "StockQuote.high_price"),
            (self.low_price, "StockQuote.low_price"),
            (self.previous_close, "StockQuote.previous_close"),
        ):
            _require_non_negative_decimal(value, field_name)

        if self.high_price < self.low_price:
            raise ValueError(
                f"StockQuote.high_price ({self.high_price!r}) must not be "
                f"below StockQuote.low_price ({self.low_price!r})"
            )

    def is_non_negative_change(self) -> bool:
        """Returns True if this quote is flat or up versus the previous close."""
        return self.change >= Decimal("0")