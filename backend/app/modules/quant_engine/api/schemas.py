"""API response schemas for the quant_engine module.

This module defines the JSON response shape returned by the technical-
analysis endpoint and provides the conversion logic from the domain
entity (``TechnicalAnalysisSnapshot``) into that shape.

The domain entity remains completely unaware of JSON or Pydantic — it is
a plain, framework-agnostic dataclass. All serialization concerns
(camelCase aliases, string-encoded Decimal values, timezone-aware
timestamps) live here, at the API boundary, following the same scoped
camelCase convention used by the ``market_data``, ``stock_search``,
``stock_details``, ``stock_history``, and ``company_fundamentals`` API
schemas.

Key serialization behaviors:

- Every optional indicator field is serialized as an exact string in
  JSON mode to avoid floating-point precision loss, and remains a
  ``Decimal`` instance in Python mode (``model_dump()``). An indicator
  that could not be calculated because its lookback window was not
  satisfied is ``null`` — it is never fabricated as ``0`` or rounded.
- ``trend`` and ``signal`` are deterministic, rule-based technical
  interpretations, not predictions, forecasts, or financial advice.
- ``calculatedAt`` and ``latestCandleAt`` are timezone-aware and are
  serialized exactly as supplied by the domain entity.

This file performs serialization only — it never calculates an
indicator, mutates the domain object, or duplicates domain validation.
"""

from decimal import Decimal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_serializer

from ..domain.entities import TechnicalAnalysisSnapshot, TechnicalSignal, TrendDirection


class TechnicalAnalysisSnapshotResponse(BaseModel):
    """A deterministic technical-analysis snapshot in the API response shape.

    Internal field names use snake_case; JSON output uses the scoped
    camelCase aliases (e.g. ``display_symbol`` -> ``displaySymbol``,
    ``fifty_two_week_high`` -> ``fiftyTwoWeekHigh``). Every optional
    Decimal field is serialized as an exact string in JSON mode to
    preserve precision; Python-mode ``model_dump()`` keeps the original
    ``Decimal`` instances. ``trend`` and ``signal`` represent mechanical,
    rule-based interpretation only, not a prediction or financial
    recommendation.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        serialize_by_alias=True,
    )

    # Identity and metadata
    symbol: str
    display_symbol: str = Field(alias="displaySymbol")
    interval: str
    currency: str | None
    candle_count: int = Field(alias="candleCount")
    latest_candle_at: AwareDatetime = Field(alias="latestCandleAt")
    calculated_at: AwareDatetime = Field(alias="calculatedAt")

    # Price reference
    current_price: Decimal = Field(alias="currentPrice")
    previous_close: Decimal | None = Field(alias="previousClose")
    price_change: Decimal | None = Field(alias="priceChange")
    price_change_percent: Decimal | None = Field(alias="priceChangePercent")

    # Trend and moving averages
    trend: TrendDirection
    sma_20: Decimal | None = Field(alias="sma20")
    sma_50: Decimal | None = Field(alias="sma50")
    sma_200: Decimal | None = Field(alias="sma200")
    ema_12: Decimal | None = Field(alias="ema12")
    ema_26: Decimal | None = Field(alias="ema26")

    # Momentum
    rsi_14: Decimal | None = Field(alias="rsi14")
    macd: Decimal | None
    macd_signal: Decimal | None = Field(alias="macdSignal")
    macd_histogram: Decimal | None = Field(alias="macdHistogram")

    # Volatility
    bollinger_upper: Decimal | None = Field(alias="bollingerUpper")
    bollinger_middle: Decimal | None = Field(alias="bollingerMiddle")
    bollinger_lower: Decimal | None = Field(alias="bollingerLower")
    atr_14: Decimal | None = Field(alias="atr14")

    # Volume
    current_volume: int | None = Field(alias="currentVolume")
    average_volume_20: Decimal | None = Field(alias="averageVolume20")
    volume_ratio: Decimal | None = Field(alias="volumeRatio")

    # Range and levels
    fifty_two_week_high: Decimal | None = Field(alias="fiftyTwoWeekHigh")
    fifty_two_week_low: Decimal | None = Field(alias="fiftyTwoWeekLow")
    nearest_support: Decimal | None = Field(alias="nearestSupport")
    nearest_resistance: Decimal | None = Field(alias="nearestResistance")

    # Overall interpretation
    signal: TechnicalSignal

    @field_serializer(
        "current_price",
        "previous_close",
        "price_change",
        "price_change_percent",
        "sma_20",
        "sma_50",
        "sma_200",
        "ema_12",
        "ema_26",
        "rsi_14",
        "macd",
        "macd_signal",
        "macd_histogram",
        "bollinger_upper",
        "bollinger_middle",
        "bollinger_lower",
        "atr_14",
        "average_volume_20",
        "volume_ratio",
        "fifty_two_week_high",
        "fifty_two_week_low",
        "nearest_support",
        "nearest_resistance",
        when_used="json",
    )
    def serialize_decimal_fields(self, value: Decimal | None) -> str | None:
        """Serialize Decimal fields as exact strings in JSON mode.

        Returns ``None`` unchanged for a missing (not-yet-calculable)
        indicator and otherwise converts the ``Decimal`` to its exact
        string representation, avoiding any floating-point rounding.
        """
        if value is None:
            return None
        return str(value)

    @classmethod
    def from_domain(
        cls,
        snapshot: TechnicalAnalysisSnapshot,
    ) -> "TechnicalAnalysisSnapshotResponse":
        """Convert a domain ``TechnicalAnalysisSnapshot`` into its API response shape.

        Maps fields directly and explicitly, with no recalculation of
        any indicator, no mutation of the domain object, and no
        substitution of missing optional values.
        """
        return cls(
            symbol=snapshot.symbol,
            displaySymbol=snapshot.display_symbol,
            interval=snapshot.interval,
            currency=snapshot.currency,
            candleCount=snapshot.candle_count,
            latestCandleAt=snapshot.latest_candle_at,
            calculatedAt=snapshot.calculated_at,
            currentPrice=snapshot.current_price,
            previousClose=snapshot.previous_close,
            priceChange=snapshot.price_change,
            priceChangePercent=snapshot.price_change_percent,
            trend=snapshot.trend,
            sma20=snapshot.sma_20,
            sma50=snapshot.sma_50,
            sma200=snapshot.sma_200,
            ema12=snapshot.ema_12,
            ema26=snapshot.ema_26,
            rsi14=snapshot.rsi_14,
            macd=snapshot.macd,
            macdSignal=snapshot.macd_signal,
            macdHistogram=snapshot.macd_histogram,
            bollingerUpper=snapshot.bollinger_upper,
            bollingerMiddle=snapshot.bollinger_middle,
            bollingerLower=snapshot.bollinger_lower,
            atr14=snapshot.atr_14,
            currentVolume=snapshot.current_volume,
            averageVolume20=snapshot.average_volume_20,
            volumeRatio=snapshot.volume_ratio,
            fiftyTwoWeekHigh=snapshot.fifty_two_week_high,
            fiftyTwoWeekLow=snapshot.fifty_two_week_low,
            nearestSupport=snapshot.nearest_support,
            nearestResistance=snapshot.nearest_resistance,
            signal=snapshot.signal,
        )