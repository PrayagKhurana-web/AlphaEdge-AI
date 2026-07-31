from datetime import datetime, timezone
from decimal import Decimal

from app.modules.quant_engine.domain.entities import (
    TechnicalAnalysisSnapshot,
    TechnicalSignal,
    TrendDirection,
)
from app.modules.stock_analysis.domain.entities import (
    StockOutlook,
    StockRiskLevel,
)
from app.modules.stock_analysis.infrastructure.calculators.stock_analysis_calculator import (
    StockAnalysisCalculator,
)


NOW = datetime(2026, 8, 1, tzinfo=timezone.utc)


def make_technical_snapshot(
    *,
    trend: TrendDirection,
    signal: TechnicalSignal,
    current_price: Decimal = Decimal("100"),
    price_change: Decimal | None = None,
    sma_20: Decimal | None = None,
    sma_50: Decimal | None = None,
    rsi_14: Decimal | None = None,
    atr_14: Decimal | None = Decimal("2"),
    volume_ratio: Decimal | None = None,
) -> TechnicalAnalysisSnapshot:
    return TechnicalAnalysisSnapshot(
        symbol="RELIANCE.NS",
        display_symbol="RELIANCE.NSE",
        interval="1d",
        currency="INR",
        candle_count=250,
        latest_candle_at=NOW,
        calculated_at=NOW,
        current_price=current_price,
        previous_close=Decimal("98"),
        price_change=price_change,
        price_change_percent=None,
        trend=trend,
        sma_20=sma_20,
        sma_50=sma_50,
        sma_200=None,
        ema_12=None,
        ema_26=None,
        rsi_14=rsi_14,
        macd=None,
        macd_signal=None,
        macd_histogram=None,
        bollinger_upper=None,
        bollinger_middle=None,
        bollinger_lower=None,
        atr_14=atr_14,
        current_volume=1_500_000,
        average_volume_20=Decimal("750000"),
        volume_ratio=volume_ratio,
        fifty_two_week_high=Decimal("120"),
        fifty_two_week_low=Decimal("70"),
        nearest_support=Decimal("95"),
        nearest_resistance=Decimal("110"),
        signal=signal,
    )


def test_calculator_produces_bullish_outlook() -> None:
    technical = make_technical_snapshot(
        trend=TrendDirection.BULLISH,
        signal=TechnicalSignal.STRONG_BUY,
        price_change=Decimal("5"),
        sma_20=Decimal("95"),
        sma_50=Decimal("90"),
        rsi_14=Decimal("55"),
        volume_ratio=Decimal("2"),
    )

    result = StockAnalysisCalculator().calculate_snapshot(
        technical=technical,
        financial=None,
    )

    assert result.outlook is StockOutlook.BULLISH
    assert result.technical_score == 97
    assert result.financial_score == 50
    assert result.market_activity_score == 75
    assert result.overall_score == 81
    assert result.bullish_probability == 72
    assert result.bearish_probability == 28
    assert result.bullish_probability + result.bearish_probability == 100


def test_calculator_produces_neutral_outlook() -> None:
    technical = make_technical_snapshot(
        trend=TrendDirection.NEUTRAL,
        signal=TechnicalSignal.NEUTRAL,
        atr_14=None,
    )

    result = StockAnalysisCalculator().calculate_snapshot(
        technical=technical,
        financial=None,
    )

    assert result.outlook is StockOutlook.NEUTRAL
    assert result.technical_score == 50
    assert result.financial_score == 50
    assert result.market_activity_score == 50
    assert result.overall_score == 50
    assert result.bullish_probability == 50
    assert result.bearish_probability == 50
    assert result.risk_level is StockRiskLevel.MEDIUM


def test_calculator_produces_bearish_outlook() -> None:
    technical = make_technical_snapshot(
        trend=TrendDirection.BEARISH,
        signal=TechnicalSignal.STRONG_SELL,
        price_change=Decimal("-5"),
        sma_20=Decimal("110"),
        sma_50=Decimal("105"),
        rsi_14=Decimal("80"),
        volume_ratio=Decimal("2"),
    )

    result = StockAnalysisCalculator().calculate_snapshot(
        technical=technical,
        financial=None,
    )

    assert result.outlook is StockOutlook.BEARISH
    assert result.technical_score == 2
    assert result.financial_score == 50
    assert result.market_activity_score == 25
    assert result.overall_score == 19
    assert result.bullish_probability == 28
    assert result.bearish_probability == 72
    assert result.bullish_probability + result.bearish_probability == 100
