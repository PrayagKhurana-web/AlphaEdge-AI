"""
Deterministic technical-analysis calculator for the quant_engine module.

This is the only file in quant_engine that computes moving averages,
momentum, volatility, volume, range, support/resistance, trend, or
overall-signal values. Every other layer depends solely on
TechnicalAnalysisCalculatorPort and quant_engine's own domain
entities/exceptions -- swapping to a different calculation strategy
later means adding a new class here that satisfies the same port; it
requires no change to application/services.py or the API layer.

This calculator performs deterministic, rule-based arithmetic only. It
does not fetch data, call any external service, persist or cache
results, or use machine learning. Its output -- including the overall
TechnicalSignal -- is a mechanical interpretation of historical price
data, not a prediction, forecast, or financial recommendation.

All externally exposed numeric results are Decimal or None. Every
conversion from a non-Decimal numeric type goes through
Decimal(str(value)), never a direct binary-float construction. Standard
deviation uses Decimal.sqrt() (decimal-context arithmetic), never a
float/math.sqrt() detour.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Final

from app.modules.quant_engine.application.ports import TechnicalAnalysisCalculatorPort
from app.modules.quant_engine.domain.entities import (
    TechnicalAnalysisSnapshot,
    TechnicalSignal,
    TrendDirection,
)
from app.modules.quant_engine.domain.exceptions import (
    InsufficientHistoricalDataError,
    InvalidHistoricalDataError,
    QuantEngineError,
    TechnicalCalculationError,
)
from app.modules.stock_history.domain.entities import HistoricalCandle, HistoricalSeries

_CALCULATOR_NAME: Final[str] = "TechnicalAnalysisCalculator"

# previous_close and price_change both require two observations; this is
# the absolute floor below which no meaningful snapshot can be produced.
# Every indicator with a longer lookback (SMA 200, RSI 14, MACD, etc.)
# degrades to None independently when its own lookback isn't satisfied --
# it does not raise.
_MINIMUM_REQUIRED_CANDLES: Final[int] = 2

_SMA_PERIODS: Final[tuple[int, ...]] = (20, 50, 200)
_EMA_PERIODS: Final[tuple[int, ...]] = (12, 26)
_RSI_PERIOD: Final[int] = 14
_MACD_FAST_PERIOD: Final[int] = 12
_MACD_SLOW_PERIOD: Final[int] = 26
_MACD_SIGNAL_PERIOD: Final[int] = 9
_BOLLINGER_PERIOD: Final[int] = 20
_BOLLINGER_STD_DEV_MULTIPLIER: Final[Decimal] = Decimal(2)
_ATR_PERIOD: Final[int] = 14
_VOLUME_AVERAGE_PERIOD: Final[int] = 20
_VOLUME_CONFIRMATION_RATIO: Final[Decimal] = Decimal("1.5")
_FIFTY_TWO_WEEK_CANDLE_WINDOW: Final[int] = 252
_PIVOT_LOOKAROUND: Final[int] = 2

_HUNDRED: Final[Decimal] = Decimal(100)
_ZERO: Final[Decimal] = Decimal(0)


class TechnicalAnalysisCalculator(TechnicalAnalysisCalculatorPort):
    """
    TechnicalAnalysisCalculatorPort implementation using only
    standard-library Decimal arithmetic -- no pandas, NumPy, TA-Lib, or
    other third-party numeric dependency is introduced.

    This class never fetches historical data; it only transforms an
    already-retrieved HistoricalSeries into a TechnicalAnalysisSnapshot.
    """

    def calculate_snapshot(
        self,
        historical_series: HistoricalSeries,
        *,
        calculated_at: datetime,
        currency: str | None,
    ) -> TechnicalAnalysisSnapshot:
        """
        Calculates a deterministic technical-analysis snapshot from
        `historical_series`.

        Args:
            historical_series: An already-retrieved candle series. Its
                symbol, display_symbol, and interval are used as-is for
                the snapshot's identity fields. Neither
                `historical_series` nor its candles are mutated.
            calculated_at: The timezone-aware moment this snapshot is
                being produced.
            currency: Used exactly as supplied; never guessed or
                fabricated.

        Returns:
            A TechnicalAnalysisSnapshot. Indicators whose lookback
            window is not satisfied by the available candle history are
            None rather than fabricated -- that is a valid outcome, not
            a calculation failure.

        Raises:
            InvalidHistoricalDataError: if `calculated_at` is not
                timezone-aware, or if `historical_series.candles`
                contains malformed, inconsistent, unordered, duplicate,
                or otherwise unusable candle data.
            InsufficientHistoricalDataError: if fewer than
                `_MINIMUM_REQUIRED_CANDLES` usable candles are available.
            TechnicalCalculationError: if an unexpected failure occurs
                during calculation despite structurally valid input.
        """
        self._validate_calculated_at(calculated_at)
        candles = self._validate_and_extract_candles(historical_series)

        try:
            return self._build_snapshot(
                historical_series,
                candles,
                calculated_at=calculated_at,
                currency=currency,
            )
        except QuantEngineError:
            raise
        except Exception as exc:
            raise TechnicalCalculationError(
                f"{_CALCULATOR_NAME}: an unexpected error occurred while "
                "calculating the technical-analysis snapshot."
            ) from exc

    # ------------------------------------------------------------------
    # Input validation
    # ------------------------------------------------------------------

    def _validate_calculated_at(self, calculated_at: datetime) -> None:
        """
        Raises:
            InvalidHistoricalDataError: if `calculated_at` is not
                timezone-aware.
        """
        if calculated_at.tzinfo is None or calculated_at.utcoffset() is None:
            raise InvalidHistoricalDataError(
                f"{_CALCULATOR_NAME}: calculated_at must be timezone-aware."
            )

    def _validate_and_extract_candles(
        self, historical_series: HistoricalSeries
    ) -> tuple[HistoricalCandle, ...]:
        """
        Validates `historical_series.candles` and returns them unchanged
        if valid.

        Raises:
            InsufficientHistoricalDataError: if there are fewer than
                `_MINIMUM_REQUIRED_CANDLES` candles.
            InvalidHistoricalDataError: if any candle timestamp is not
                timezone-aware, timestamps are not strictly increasing,
                any required OHLC value is non-finite or not strictly
                positive, the high/low relationship is violated, or
                volume is negative.
        """
        candles = historical_series.candles

        if len(candles) < _MINIMUM_REQUIRED_CANDLES:
            raise InsufficientHistoricalDataError(
                f"{_CALCULATOR_NAME}: not enough usable candles to "
                "calculate a technical-analysis snapshot.",
                available_candle_count=len(candles),
                required_candle_count=_MINIMUM_REQUIRED_CANDLES,
            )

        previous_timestamp = None
        for index, candle in enumerate(candles):
            if candle.timestamp.tzinfo is None or candle.timestamp.utcoffset() is None:
                raise InvalidHistoricalDataError(
                    f"{_CALCULATOR_NAME}: candle at index {index} has a "
                    "timestamp that is not timezone-aware."
                )
            if previous_timestamp is not None and candle.timestamp <= previous_timestamp:
                raise InvalidHistoricalDataError(
                    f"{_CALCULATOR_NAME}: candle timestamps are not "
                    f"strictly increasing at index {index} (duplicate or "
                    "out-of-order timestamp)."
                )
            previous_timestamp = candle.timestamp

            for field_name, value in (
                ("open", candle.open_price),
                ("high", candle.high_price),
                ("low", candle.low_price),
                ("close", candle.close_price),
            ):
                if (
                    not isinstance(value, Decimal)
                    or not value.is_finite()
                    or value <= 0
                ):
                    raise InvalidHistoricalDataError(
                        f"{_CALCULATOR_NAME}: candle at index {index} has "
                        f"a non-finite or non-positive {field_name!r} value."
                    )

            if (
                candle.high_price < candle.open_price
                or candle.high_price < candle.close_price
                or candle.high_price < candle.low_price
            ):
                raise InvalidHistoricalDataError(
                    f"{_CALCULATOR_NAME}: candle at index {index} has a "
                    "high price lower than one of open/close/low."
                )
            if (
                candle.low_price > candle.open_price
                or candle.low_price > candle.close_price
                or candle.low_price > candle.high_price
            ):
                raise InvalidHistoricalDataError(
                    f"{_CALCULATOR_NAME}: candle at index {index} has a "
                    "low price higher than one of open/close/high."
                )

            if candle.volume is not None and candle.volume < 0:
                raise InvalidHistoricalDataError(
                    f"{_CALCULATOR_NAME}: candle at index {index} has a "
                    "negative volume."
                )

        return candles

    # ------------------------------------------------------------------
    # Orchestration of the individual indicator groups
    # ------------------------------------------------------------------

    def _build_snapshot(
        self,
        historical_series: HistoricalSeries,
        candles: tuple[HistoricalCandle, ...],
        *,
        calculated_at: datetime,
        currency: str | None,
    ) -> TechnicalAnalysisSnapshot:
        """Calculates every indicator group and assembles the snapshot."""
        closes = [candle.close_price for candle in candles]

        current_price = closes[-1]
        previous_close = closes[-2] if len(closes) >= 2 else None
        price_change, price_change_percent = self._calculate_price_change(
            current_price, previous_close
        )

        sma_20 = self._calculate_sma(closes, 20)
        sma_50 = self._calculate_sma(closes, 50)
        sma_200 = self._calculate_sma(closes, 200)

        ema_12_series = self._calculate_ema_series(closes, _MACD_FAST_PERIOD)
        ema_26_series = self._calculate_ema_series(closes, _MACD_SLOW_PERIOD)
        ema_12 = ema_12_series[-1] if ema_12_series else None
        ema_26 = ema_26_series[-1] if ema_26_series else None
        rsi_14 = self._calculate_rsi(closes)

        macd, macd_signal, macd_histogram = self._calculate_macd(
            ema_12_series, ema_26_series
        )

        bollinger_upper, bollinger_middle, bollinger_lower = (
            self._calculate_bollinger_bands(closes)
        )

        atr_14 = self._calculate_atr(candles)

        current_volume, average_volume_20, volume_ratio = self._calculate_volume_metrics(
            candles
        )

        fifty_two_week_high, fifty_two_week_low = self._calculate_fifty_two_week_range(
            candles
        )

        nearest_support, nearest_resistance = self._calculate_support_resistance(
            candles, current_price
        )

        trend = self._calculate_trend(current_price, sma_20, sma_50)
        signal = self._calculate_signal(
            trend=trend,
            current_price=current_price,
            sma_20=sma_20,
            rsi_14=rsi_14,
            macd=macd,
            macd_signal=macd_signal,
            volume_ratio=volume_ratio,
        )

        return TechnicalAnalysisSnapshot(
            symbol=historical_series.symbol,
            display_symbol=historical_series.display_symbol,
            interval=historical_series.interval,
            currency=currency,
            candle_count=len(candles),
            latest_candle_at=candles[-1].timestamp,
            calculated_at=calculated_at,
            current_price=current_price,
            previous_close=previous_close,
            price_change=price_change,
            price_change_percent=price_change_percent,
            trend=trend,
            sma_20=sma_20,
            sma_50=sma_50,
            sma_200=sma_200,
            ema_12=ema_12,
            ema_26=ema_26,
            rsi_14=rsi_14,
            macd=macd,
            macd_signal=macd_signal,
            macd_histogram=macd_histogram,
            bollinger_upper=bollinger_upper,
            bollinger_middle=bollinger_middle,
            bollinger_lower=bollinger_lower,
            atr_14=atr_14,
            current_volume=current_volume,
            average_volume_20=average_volume_20,
            volume_ratio=volume_ratio,
            fifty_two_week_high=fifty_two_week_high,
            fifty_two_week_low=fifty_two_week_low,
            nearest_support=nearest_support,
            nearest_resistance=nearest_resistance,
            signal=signal,
        )

    # ------------------------------------------------------------------
    # Price change
    # ------------------------------------------------------------------

    def _calculate_price_change(
        self,
        current_price: Decimal,
        previous_close: Decimal | None,
    ) -> tuple[Decimal | None, Decimal | None]:
        """Returns (price_change, price_change_percent), unrounded."""
        if previous_close is None:
            return None, None
        price_change = current_price - previous_close
        price_change_percent = (price_change / previous_close) * _HUNDRED
        return price_change, price_change_percent

    # ------------------------------------------------------------------
    # Simple moving average
    # ------------------------------------------------------------------

    def _calculate_sma(self, closes: list[Decimal], period: int) -> Decimal | None:
        """Arithmetic mean of the latest `period` closes, or None."""
        if len(closes) < period:
            return None
        window = closes[-period:]
        return sum(window, _ZERO) / Decimal(period)

    # ------------------------------------------------------------------
    # Exponential moving average
    # ------------------------------------------------------------------

    def _calculate_ema_series(self, values: list[Decimal], period: int) -> list[Decimal]:
        """
        Calculates the full EMA series for `values` using the
        conventional multiplier 2 / (period + 1), seeded with the SMA of
        the first `period` values.

        Returns an empty list if fewer than `period` values are
        available. `ema_series[0]` corresponds to the seed (covering
        `values[:period]`); each subsequent entry processes one more
        value in chronological order. The latest EMA is `ema_series[-1]`.
        """
        if len(values) < period:
            return []

        multiplier = Decimal(2) / Decimal(period + 1)
        seed = sum(values[:period], _ZERO) / Decimal(period)

        ema_series = [seed]
        for value in values[period:]:
            previous_ema = ema_series[-1]
            ema_series.append((value - previous_ema) * multiplier + previous_ema)

        return ema_series

    # ------------------------------------------------------------------
    # RSI (Wilder-style)
    # ------------------------------------------------------------------

    def _calculate_rsi(self, closes: list[Decimal]) -> Decimal | None:
        """
        Wilder-style RSI over `_RSI_PERIOD` periods. Returns None if
        fewer than `_RSI_PERIOD` + 1 closes are available (14 price
        changes require 15 closes).
        """
        if len(closes) < _RSI_PERIOD + 1:
            return None

        changes = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
        gains = [change if change > 0 else _ZERO for change in changes]
        losses = [-change if change < 0 else _ZERO for change in changes]

        average_gain = sum(gains[:_RSI_PERIOD], _ZERO) / Decimal(_RSI_PERIOD)
        average_loss = sum(losses[:_RSI_PERIOD], _ZERO) / Decimal(_RSI_PERIOD)

        for index in range(_RSI_PERIOD, len(changes)):
            average_gain = (
                average_gain * (_RSI_PERIOD - 1) + gains[index]
            ) / Decimal(_RSI_PERIOD)
            average_loss = (
                average_loss * (_RSI_PERIOD - 1) + losses[index]
            ) / Decimal(_RSI_PERIOD)

        if average_loss == 0 and average_gain > 0:
            return _HUNDRED
        if average_gain == 0 and average_loss == 0:
            return Decimal(50)

        relative_strength = average_gain / average_loss
        return _HUNDRED - (_HUNDRED / (Decimal(1) + relative_strength))

    # ------------------------------------------------------------------
    # MACD
    # ------------------------------------------------------------------

    def _calculate_macd(
        self,
        ema_12_series: list[Decimal],
        ema_26_series: list[Decimal],
    ) -> tuple[Decimal | None, Decimal | None, Decimal | None]:
        """
        Calculates (macd, macd_signal, macd_histogram) from the full
        EMA-12 and EMA-26 series.

        The MACD line series is EMA-12 minus EMA-26 at each point where
        both exist -- `ema_12_series` starts `_MACD_SLOW_PERIOD -
        _MACD_FAST_PERIOD` entries earlier than `ema_26_series`, so it is
        offset by that amount before subtracting. The signal line is the
        EMA-9 of that MACD series. All three fields are None together
        unless the signal line itself can be produced.
        """
        if not ema_12_series or not ema_26_series:
            return None, None, None

        offset = _MACD_SLOW_PERIOD - _MACD_FAST_PERIOD
        macd_series = [
            ema_12_series[offset + index] - ema_26_value
            for index, ema_26_value in enumerate(ema_26_series)
        ]

        signal_series = self._calculate_ema_series(macd_series, _MACD_SIGNAL_PERIOD)
        if not signal_series:
            return None, None, None

        macd_line = macd_series[-1]
        macd_signal = signal_series[-1]
        macd_histogram = macd_line - macd_signal
        return macd_line, macd_signal, macd_histogram

    # ------------------------------------------------------------------
    # Bollinger Bands
    # ------------------------------------------------------------------

    def _calculate_bollinger_bands(
        self, closes: list[Decimal]
    ) -> tuple[Decimal | None, Decimal | None, Decimal | None]:
        """
        Calculates (upper, middle, lower) Bollinger Bands over the
        latest `_BOLLINGER_PERIOD` closes, using population standard
        deviation. Returns (None, None, None) if fewer than
        `_BOLLINGER_PERIOD` closes are available. Standard deviation is
        computed via Decimal.sqrt(), never a float/math.sqrt() detour.
        """
        if len(closes) < _BOLLINGER_PERIOD:
            return None, None, None

        window = closes[-_BOLLINGER_PERIOD:]
        middle = sum(window, _ZERO) / Decimal(_BOLLINGER_PERIOD)
        variance = sum(((value - middle) ** 2 for value in window), _ZERO) / Decimal(
            _BOLLINGER_PERIOD
        )
        standard_deviation = variance.sqrt()

        upper = middle + _BOLLINGER_STD_DEV_MULTIPLIER * standard_deviation
        lower = middle - _BOLLINGER_STD_DEV_MULTIPLIER * standard_deviation
        return upper, middle, lower

    # ------------------------------------------------------------------
    # ATR (Wilder-style)
    # ------------------------------------------------------------------

    def _calculate_atr(self, candles: tuple[HistoricalCandle, ...]) -> Decimal | None:
        """
        Wilder-style Average True Range over `_ATR_PERIOD` periods.
        Returns None if fewer than `_ATR_PERIOD` candles are available.
        The first candle's true range is high - low (no previous close
        exists); every subsequent candle uses the standard three-way
        true-range formula against the prior candle's close.
        """
        if len(candles) < _ATR_PERIOD:
            return None

        true_ranges: list[Decimal] = []
        for index, candle in enumerate(candles):
            if index == 0:
                true_range = candle.high_price - candle.low_price
            else:
                previous_close = candles[index - 1].close_price
                true_range = max(
                    candle.high_price - candle.low_price,
                    abs(candle.high_price - previous_close),
                    abs(candle.low_price - previous_close),
                )
            true_ranges.append(true_range)

        atr = sum(true_ranges[:_ATR_PERIOD], _ZERO) / Decimal(_ATR_PERIOD)
        for true_range in true_ranges[_ATR_PERIOD:]:
            atr = (atr * (_ATR_PERIOD - 1) + true_range) / Decimal(_ATR_PERIOD)

        return atr

    # ------------------------------------------------------------------
    # Volume
    # ------------------------------------------------------------------

    def _calculate_volume_metrics(
        self, candles: tuple[HistoricalCandle, ...]
    ) -> tuple[int | None, Decimal | None, Decimal | None]:
        """
        Returns (current_volume, average_volume_20, volume_ratio).

        `current_volume` is the latest candle's volume, which may itself
        be None if unavailable. `average_volume_20` is the mean of the
        latest `_VOLUME_AVERAGE_PERIOD` candle volumes, but only when
        every one of those candles has a usable (non-null) volume --
        otherwise None. `volume_ratio` is
        current_volume / average_volume_20, computed only when both
        `current_volume` and `average_volume_20` are available and
        `average_volume_20` is strictly positive. Missing volume is
        never fabricated as zero.
        """
        current_volume = candles[-1].volume

        if len(candles) < _VOLUME_AVERAGE_PERIOD:
            return current_volume, None, None

        recent_volumes = [candle.volume for candle in candles[-_VOLUME_AVERAGE_PERIOD:]]
        if any(volume is None for volume in recent_volumes):
            return current_volume, None, None

        average_volume_20 = sum(
            (Decimal(volume) for volume in recent_volumes), _ZERO
        ) / Decimal(_VOLUME_AVERAGE_PERIOD)

        if current_volume is None or average_volume_20 <= 0:
            return current_volume, average_volume_20, None

        volume_ratio = Decimal(current_volume) / average_volume_20
        return current_volume, average_volume_20, volume_ratio

    # ------------------------------------------------------------------
    # Fifty-two-week range
    # ------------------------------------------------------------------

    def _calculate_fifty_two_week_range(
        self, candles: tuple[HistoricalCandle, ...]
    ) -> tuple[Decimal, Decimal]:
        """
        Returns (fifty_two_week_high, fifty_two_week_low) from the
        latest `_FIFTY_TWO_WEEK_CANDLE_WINDOW` candles, or all available
        candles when fewer exist. This is documented as an
        available-history range rather than a literal calendar 52-week
        range: with fewer than 252 candles, or with a non-daily
        interval, the window does not necessarily span exactly 52 weeks
        of trading.
        """
        window = candles[-_FIFTY_TWO_WEEK_CANDLE_WINDOW:]
        fifty_two_week_high = max(candle.high_price for candle in window)
        fifty_two_week_low = min(candle.low_price for candle in window)
        return fifty_two_week_high, fifty_two_week_low

    # ------------------------------------------------------------------
    # Support and resistance (confirmed pivots)
    # ------------------------------------------------------------------

    def _calculate_support_resistance(
        self,
        candles: tuple[HistoricalCandle, ...],
        current_price: Decimal,
    ) -> tuple[Decimal | None, Decimal | None]:
        """
        Returns (nearest_support, nearest_resistance) using confirmed
        local pivot levels: a pivot low/high requires
        `_PIVOT_LOOKAROUND` candles on both sides to confirm it, so the
        first and last `_PIVOT_LOOKAROUND` candles can never be pivots.
        Nearest support is the greatest confirmed pivot low at or below
        `current_price`; nearest resistance is the smallest confirmed
        pivot high at or above `current_price`. Returns None for either
        side when no qualifying confirmed level exists -- no level is
        ever invented from an arbitrary percentage.
        """
        pivot_lows: list[Decimal] = []
        pivot_highs: list[Decimal] = []

        for index in range(_PIVOT_LOOKAROUND, len(candles) - _PIVOT_LOOKAROUND):
            candidate = candles[index]
            neighbors = (
                candles[index - _PIVOT_LOOKAROUND : index]
                + candles[index + 1 : index + _PIVOT_LOOKAROUND + 1]
            )

            if all(candidate.low_price <= other.low_price for other in neighbors):
                pivot_lows.append(candidate.low_price)
            if all(candidate.high_price >= other.high_price for other in neighbors):
                pivot_highs.append(candidate.high_price)

        eligible_supports = [low for low in pivot_lows if low <= current_price]
        eligible_resistances = [high for high in pivot_highs if high >= current_price]

        nearest_support = max(eligible_supports) if eligible_supports else None
        nearest_resistance = (
            min(eligible_resistances) if eligible_resistances else None
        )
        return nearest_support, nearest_resistance

    # ------------------------------------------------------------------
    # Trend
    # ------------------------------------------------------------------

    def _calculate_trend(
        self,
        current_price: Decimal,
        sma_20: Decimal | None,
        sma_50: Decimal | None,
    ) -> TrendDirection:
        """
        Deterministic trend rule based only on already-calculated moving
        averages -- never on future values.

        bullish: current_price > sma_20, and sma_20 > sma_50 when sma_50
            exists.
        bearish: current_price < sma_20, and sma_20 < sma_50 when sma_50
            exists.
        neutral: otherwise, including when sma_20 is unavailable.
        """
        if sma_20 is None:
            return TrendDirection.NEUTRAL

        if current_price > sma_20 and (sma_50 is None or sma_20 > sma_50):
            return TrendDirection.BULLISH
        if current_price < sma_20 and (sma_50 is None or sma_20 < sma_50):
            return TrendDirection.BEARISH
        return TrendDirection.NEUTRAL

    # ------------------------------------------------------------------
    # Overall signal
    # ------------------------------------------------------------------

    def _calculate_signal(
        self,
        *,
        trend: TrendDirection,
        current_price: Decimal,
        sma_20: Decimal | None,
        rsi_14: Decimal | None,
        macd: Decimal | None,
        macd_signal: Decimal | None,
        volume_ratio: Decimal | None,
    ) -> TechnicalSignal:
        """
        Combines available indicators into a single deterministic
        TechnicalSignal via an explicit point score. This is a mechanical
        interpretation of the indicators already calculated above, not a
        forecast or financial recommendation. The underlying score is
        intentionally not exposed, since TechnicalAnalysisSnapshot has
        no score field.
        """
        score = 0

        if trend is TrendDirection.BULLISH:
            score += 2
        elif trend is TrendDirection.BEARISH:
            score -= 2

        if rsi_14 is not None:
            if rsi_14 < 30:
                score += 1
            elif rsi_14 > 70:
                score -= 1

        if macd is not None and macd_signal is not None:
            if macd > macd_signal:
                score += 1
            elif macd < macd_signal:
                score -= 1

        if sma_20 is not None:
            if current_price > sma_20:
                score += 1
            elif current_price < sma_20:
                score -= 1

        if volume_ratio is not None and volume_ratio >= _VOLUME_CONFIRMATION_RATIO:
            if score > 0:
                score += 1
            elif score < 0:
                score -= 1

        if score >= 4:
            return TechnicalSignal.STRONG_BUY
        if score >= 2:
            return TechnicalSignal.BUY
        if score <= -4:
            return TechnicalSignal.STRONG_SELL
        if score <= -2:
            return TechnicalSignal.SELL
        return TechnicalSignal.NEUTRAL