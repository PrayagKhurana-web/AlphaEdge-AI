"""Domain entities for the quant_engine module.

Defines a framework-agnostic technical-analysis snapshot calculated from
historical OHLCV candle data. This module has no awareness of FastAPI,
Pydantic, JSON, httpx, Yahoo Finance, pandas, NumPy, TA-Lib, database
models, caching, or HTTP status codes -- it defines data structures
only. Calculating any of the indicator values held here (SMA, EMA, RSI,
MACD, Bollinger Bands, ATR, trend, support/resistance, or the overall
signal) is the responsibility of a later application/domain service
layer, not this file.

This first iteration is deliberately limited to a deterministic
technical-analysis snapshot: no machine learning, prediction
probabilities, backtesting, portfolio logic, broker logic, alerts, or
AI-generated analysis.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum


class TrendDirection(str, Enum):
    """The overall directional trend implied by a technical snapshot."""

    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class TechnicalSignal(str, Enum):
    """A deterministic, rule-based technical interpretation.

    This represents mechanical technical interpretation only -- it is
    derived from fixed rules applied to indicator values, not a
    prediction, forecast, or guarantee of future returns, and must not
    be presented as financial advice.
    """

    STRONG_BUY = "strong_buy"
    BUY = "buy"
    NEUTRAL = "neutral"
    SELL = "sell"
    STRONG_SELL = "strong_sell"


@dataclass(frozen=True, slots=True)
class TechnicalAnalysisSnapshot:
    """A point-in-time technical-analysis snapshot for a stock.

    Computed from historical OHLCV candle data as of ``calculated_at``.
    Any indicator this snapshot cannot compute (e.g. insufficient candle
    history for a given lookback window) is represented as ``None``
    rather than a fabricated value. All numeric fields use ``Decimal``
    and remain exactly as calculated -- no rounding, scaling, or
    reformatting is applied here. ``interval`` mirrors stock_history's
    own representation of candle interval, which is a plain string
    (e.g. "1d") rather than an enum, so it is reused as-is here rather
    than introducing a new quant_engine-owned type.
    """

    # Identity and metadata
    symbol: str
    display_symbol: str
    interval: str
    currency: str | None
    candle_count: int
    latest_candle_at: datetime
    calculated_at: datetime

    # Price reference
    current_price: Decimal
    previous_close: Decimal | None
    price_change: Decimal | None
    price_change_percent: Decimal | None

    # Trend and moving averages
    trend: TrendDirection
    sma_20: Decimal | None
    sma_50: Decimal | None
    sma_200: Decimal | None
    ema_12: Decimal | None
    ema_26: Decimal | None

    # Momentum
    rsi_14: Decimal | None
    macd: Decimal | None
    macd_signal: Decimal | None
    macd_histogram: Decimal | None

    # Volatility
    bollinger_upper: Decimal | None
    bollinger_middle: Decimal | None
    bollinger_lower: Decimal | None
    atr_14: Decimal | None

    # Volume
    current_volume: int | None
    average_volume_20: Decimal | None
    volume_ratio: Decimal | None

    # Range and levels
    fifty_two_week_high: Decimal | None
    fifty_two_week_low: Decimal | None
    nearest_support: Decimal | None
    nearest_resistance: Decimal | None

    # Overall interpretation
    signal: TechnicalSignal

    def __post_init__(self) -> None:
        """Enforce structural invariants on the assembled snapshot.

        Raises:
            ValueError: if any of the following hold: `symbol` or
                `display_symbol` is empty; `candle_count` is not
                positive; `latest_candle_at` or `calculated_at` is not
                timezone-aware; `current_price` is not strictly
                positive; `current_volume` is present and negative;
                `fifty_two_week_low` exceeds `fifty_two_week_high` when
                both are present; or the Bollinger Band values are
                present but not ordered lower <= middle <= upper.
        """
        if not self.symbol.strip():
            raise ValueError("symbol must not be empty")
        if not self.display_symbol.strip():
            raise ValueError("display_symbol must not be empty")
        if self.candle_count <= 0:
            raise ValueError(
                f"candle_count must be positive, got {self.candle_count!r}"
            )
        if self.latest_candle_at.tzinfo is None:
            raise ValueError("latest_candle_at must be timezone-aware")
        if self.calculated_at.tzinfo is None:
            raise ValueError("calculated_at must be timezone-aware")
        if self.current_price <= 0:
            raise ValueError(
                f"current_price must be strictly positive, got "
                f"{self.current_price!r}"
            )
        if self.current_volume is not None and self.current_volume < 0:
            raise ValueError(
                f"current_volume must not be negative, got "
                f"{self.current_volume!r}"
            )
        if (
            self.fifty_two_week_high is not None
            and self.fifty_two_week_low is not None
            and self.fifty_two_week_low > self.fifty_two_week_high
        ):
            raise ValueError(
                "fifty_two_week_low must not exceed fifty_two_week_high "
                f"(got low={self.fifty_two_week_low!r}, "
                f"high={self.fifty_two_week_high!r})"
            )
        if (
            self.bollinger_lower is not None
            and self.bollinger_middle is not None
            and self.bollinger_upper is not None
            and not (
                self.bollinger_lower
                <= self.bollinger_middle
                <= self.bollinger_upper
            )
        ):
            raise ValueError(
                "bollinger_lower must not exceed bollinger_middle, and "
                "bollinger_middle must not exceed bollinger_upper (got "
                f"lower={self.bollinger_lower!r}, "
                f"middle={self.bollinger_middle!r}, "
                f"upper={self.bollinger_upper!r})"
            )