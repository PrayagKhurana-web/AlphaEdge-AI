"""API response schemas for the stock_history module.

This module defines the JSON response shape returned by the historical
stock candle endpoint and provides the conversion logic from domain
entities (``HistoricalCandle`` / ``HistoricalSeries``) into that shape.

Domain entities remain completely unaware of JSON or Pydantic — they are
plain, framework-agnostic objects. All serialization concerns (camelCase
aliases, string-encoded Decimal prices, timezone-aware timestamps) live
here, at the API boundary, following the same scoped camelCase convention
used by the ``market_data``, ``stock_search``, and ``stock_details`` API
schemas.

Key serialization behaviors:

- Price fields (``open``, ``high``, ``low``, ``close``, ``adjustedClose``)
  are serialized as exact strings in JSON mode to avoid floating-point
  precision loss. In Python mode (``model_dump()``), the underlying
  ``Decimal`` instances are preserved unchanged.
- ``adjustedClose`` may be ``null`` when no adjusted close is available
  for a given candle.
- Candle ordering is preserved exactly as provided by the domain layer —
  this module never sorts, deduplicates, recalculates, or rounds values.
- Timestamps (``timestamp``, ``fetchedAt``) are timezone-aware
  (``AwareDatetime``).
"""

from decimal import Decimal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_serializer

from ..domain.entities import HistoricalCandle, HistoricalSeries
from ...stock_search.domain.entities import StockExchange


class HistoricalCandleResponse(BaseModel):
    """A single OHLCV candle in the historical series API response.

    Internal field names use snake_case; JSON output uses the scoped
    camelCase aliases (e.g. ``open_price`` -> ``open``,
    ``adjusted_close`` -> ``adjustedClose``). Decimal price fields are
    serialized as exact strings in JSON mode to preserve precision;
    Python-mode ``model_dump()`` keeps the original ``Decimal`` instances.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        serialize_by_alias=True,
    )

    timestamp: AwareDatetime
    open_price: Decimal = Field(alias="open")
    high_price: Decimal = Field(alias="high")
    low_price: Decimal = Field(alias="low")
    close_price: Decimal = Field(alias="close")
    adjusted_close: Decimal | None = Field(alias="adjustedClose")
    volume: int

    @field_serializer(
        "open_price",
        "high_price",
        "low_price",
        "close_price",
        "adjusted_close",
        when_used="json",
    )
    def serialize_decimal_fields(self, value: Decimal | None) -> str | None:
        """Serialize Decimal price fields as exact strings in JSON mode.

        Returns ``None`` unchanged (for an absent ``adjusted_close``) and
        otherwise converts the ``Decimal`` to its exact string
        representation, avoiding any floating-point rounding.
        """
        if value is None:
            return None
        return str(value)

    @classmethod
    def from_domain(cls, candle: HistoricalCandle) -> "HistoricalCandleResponse":
        """Convert a domain ``HistoricalCandle`` into its API response shape.

        Maps fields directly with no recalculation, rounding, or
        reformatting of values.
        """
        return cls(
            timestamp=candle.timestamp,
            open=candle.open_price,
            high=candle.high_price,
            low=candle.low_price,
            close=candle.close_price,
            adjustedClose=candle.adjusted_close,
            volume=candle.volume,
        )


class HistoricalSeriesResponse(BaseModel):
    """The full historical candle series returned by the history endpoint.

    Internal field names use snake_case; JSON output uses the scoped
    camelCase aliases (e.g. ``display_symbol`` -> ``displaySymbol``,
    ``fetched_at`` -> ``fetchedAt``), following the same convention used
    by the ``market_data``, ``stock_search``, and ``stock_details`` API
    schemas. Candle ordering is preserved exactly as provided by the
    domain layer — this model never sorts or deduplicates candles.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        serialize_by_alias=True,
    )

    symbol: str
    display_symbol: str = Field(alias="displaySymbol")
    company_name: str = Field(alias="companyName")
    exchange: StockExchange
    interval: str
    period: str
    candles: list[HistoricalCandleResponse]
    fetched_at: AwareDatetime = Field(alias="fetchedAt")

    @classmethod
    def from_domain(cls, series: HistoricalSeries) -> "HistoricalSeriesResponse":
        """Convert a domain ``HistoricalSeries`` into its API response shape.

        Converts the tuple of domain candles into a list of
        ``HistoricalCandleResponse`` instances, preserving order exactly.
        No sorting, deduplication, recalculation, rounding, or default
        values are applied.
        """
        return cls(
            symbol=series.symbol,
            displaySymbol=series.display_symbol,
            companyName=series.company_name,
            exchange=series.exchange,
            interval=series.interval,
            period=series.period,
            candles=[
                HistoricalCandleResponse.from_domain(candle)
                for candle in series.candles
            ],
            fetchedAt=series.fetched_at,
        )