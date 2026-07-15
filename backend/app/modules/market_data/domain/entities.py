"""
Domain entities for the market_data module's live index tracking capability.

These are pure Python objects with zero framework dependencies (no FastAPI,
no SQLAlchemy, no HTTP client). They represent the concept of a "market index
quote" independent of where the data came from or how it's transported.
Per PROJECT_CONTEXT.md's Clean Architecture rule, this file must never import
from application/, infrastructure/, or api/.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from types import MappingProxyType


class IndexSymbol(str, Enum):
    """
    Canonical, provider-agnostic identifiers for the indices this module
    supports. Application and infrastructure code should reference these
    enum members rather than raw strings, so adding a new index later is a
    one-line addition here rather than a hunt through string literals.

    This enum is deliberately small for Sprint 3. Extending it (e.g. adding
    NIFTY_IT, NIFTY_AUTO) does not require touching any other layer's
    interfaces -- only the infrastructure-layer symbol mapping needs a new
    entry.
    """

    NIFTY_50 = "nifty50"
    SENSEX = "sensex"
    BANK_NIFTY = "bankNifty"
    INDIA_VIX = "indiaVix"


def _require_utc_datetime(value: datetime, field_name: str) -> None:
    """
    Raises ValueError unless `value` is a timezone-aware datetime whose
    UTC offset is exactly zero.

    This rejects two distinct problem cases:
      1. Naive datetimes (no tzinfo at all) -- a common source of silent
         bugs when data crosses between a provider (which may return naive
         local-time values), storage, and display.
      2. Timezone-aware datetimes that aren't UTC (e.g. IST, +05:30) --
         DATABASE.md's TIMESTAMPTZ convention stores everything in UTC, so
         this module standardizes on UTC at the domain boundary rather than
         relying on every downstream consumer to convert correctly.

    Any tzinfo implementation is accepted as long as its computed offset
    for this value is zero (e.g. both datetime.timezone.utc and
    zoneinfo.ZoneInfo("UTC") pass) -- the check is on the resulting offset,
    not on object identity with a specific tzinfo class.
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


@dataclass(frozen=True, slots=True)
class IndexQuote:
    """
    A single point-in-time quote for one market index.

    Attributes:
        symbol: The canonical index identifier (provider-agnostic).
        display_name: Human-readable name for UI display (e.g. "NIFTY 50").
        price: Last traded price, as a Decimal to avoid floating-point
            rounding error in downstream calculations (consistent with
            DATABASE.md's rule that monetary/price values never use floats).
        change: Absolute change from the previous close, same precision
            rationale as `price`.
        change_percent: Percentage change from the previous close.
        as_of: UTC timestamp (timezone-aware, zero offset) of when this
            quote was observed/fetched -- distinct from "now", since a
            provider may return slightly stale data during market hours or
            a cached value outside them.

    Raises:
        ValueError: if `as_of` is not a UTC (zero-offset), timezone-aware
            datetime.
    """

    symbol: IndexSymbol
    display_name: str
    price: Decimal
    change: Decimal
    change_percent: Decimal
    as_of: datetime

    def __post_init__(self) -> None:
        _require_utc_datetime(self.as_of, "IndexQuote.as_of")

    def is_non_negative(self) -> bool:
        """Returns True if this index is flat or up versus the previous close."""
        return self.change >= Decimal("0")


@dataclass(frozen=True, slots=True)
class MarketIndicesSnapshot:
    """
    An aggregate of all tracked index quotes at a single point in time --
    this is the domain-level shape that the API's response schema (api/schemas.py)
    will be built from, but this object itself knows nothing about JSON,
    HTTP, or the exact response field names the API contract uses.

    Attributes:
        quotes: Truly read-only view of each tracked index's current quote.
            The mapping supplied to the constructor is defensively copied
            and wrapped in a types.MappingProxyType, so neither of the
            following can mutate this snapshot after construction:
              - attempting to write through `snapshot.quotes[...] = ...`
                (rejected by MappingProxyType itself)
              - mutating the original dict the caller passed in after
                construction (has no effect, since a copy was stored)
        generated_at: UTC timestamp (timezone-aware, zero offset) of when
            this snapshot was assembled, which may be slightly later than
            each individual quote's `as_of` if quotes were fetched at
            slightly different times.

    Raises:
        ValueError: if `generated_at` is not a UTC (zero-offset),
            timezone-aware datetime.
    """

    quotes: Mapping[IndexSymbol, IndexQuote]
    generated_at: datetime

    def __post_init__(self) -> None:
        _require_utc_datetime(self.generated_at, "MarketIndicesSnapshot.generated_at")

        # The dataclass is frozen, so normal attribute assignment
        # (self.quotes = ...) is disallowed even inside __post_init__.
        # object.__setattr__ bypasses that restriction for this one,
        # intentional, controlled write. We copy the caller's mapping
        # first (so later mutation of their original dict can't leak
        # into this snapshot), then wrap the copy in MappingProxyType
        # (so the snapshot's own `quotes` attribute can't be written
        # through either).
        immutable_quotes = MappingProxyType(dict(self.quotes))
        object.__setattr__(self, "quotes", immutable_quotes)

    def get(self, symbol: IndexSymbol) -> IndexQuote | None:
        """
        Returns the quote for a given index if present in this snapshot,
        or None if that index's data was unavailable when the snapshot was
        assembled (e.g. one provider call failed while others succeeded).
        """
        return self.quotes.get(symbol)