from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.modules.prediction_engine.application.services import (
    PredictionDatasetBuilder,
)
from app.modules.prediction_engine.domain.entities import (
    DirectionLabel,
    PredictionHorizon,
)
from app.modules.stock_history.domain.entities import (
    HistoricalCandle,
    HistoricalSeries,
)
from app.modules.stock_search.domain.entities import StockExchange


START = datetime(2026, 1, 1, tzinfo=timezone.utc)


def make_series(
    *,
    candle_count: int = 30,
    daily_growth: Decimal = Decimal("0.01"),
) -> HistoricalSeries:
    candles: list[HistoricalCandle] = []
    close = Decimal("100")

    for index in range(candle_count):
        open_price = close
        close = close * (
            Decimal("1") + daily_growth
        )

        candles.append(
            HistoricalCandle(
                timestamp=START + timedelta(days=index),
                open_price=open_price,
                high_price=close + Decimal("1"),
                low_price=open_price - Decimal("1"),
                close_price=close,
                adjusted_close=close,
                volume=1_000 + (index * 10),
            )
        )

    return HistoricalSeries(
        symbol="RELIANCE",
        display_symbol="RELIANCE.NSE",
        company_name="Reliance Industries",
        exchange=StockExchange.NSE,
        interval="1d",
        period="1y",
        candles=tuple(candles),
        fetched_at=START + timedelta(days=candle_count),
    )


def test_builder_creates_leakage_safe_rows() -> None:
    series = make_series(candle_count=30)

    dataset = PredictionDatasetBuilder().build(
        series,
        horizon=PredictionHorizon.FIVE_SESSIONS,
        positive_threshold=Decimal("0.03"),
        negative_threshold=Decimal("-0.03"),
    )

    # Indexes 20 through 24 are usable:
    # 20 prior sessions are required and 5 future sessions are required.
    assert len(dataset.rows) == 5

    first_row = dataset.rows[0]

    assert first_row.as_of == series.candles[20].timestamp
    assert first_row.close_price == series.candles[20].close_price
    assert first_row.future_return == (
        series.candles[25].close_price
        / series.candles[20].close_price
        - Decimal("1")
    )


def test_builder_excludes_rows_without_future_outcome() -> None:
    series = make_series(candle_count=30)

    dataset = PredictionDatasetBuilder().build(
        series,
        horizon=PredictionHorizon.TWENTY_SESSIONS,
        positive_threshold=Decimal("0.05"),
        negative_threshold=Decimal("-0.05"),
    )

    assert dataset.rows == ()


def test_builder_labels_positive_growth_as_bullish() -> None:
    series = make_series(
        candle_count=30,
        daily_growth=Decimal("0.02"),
    )

    dataset = PredictionDatasetBuilder().build(
        series,
        horizon=PredictionHorizon.FIVE_SESSIONS,
        positive_threshold=Decimal("0.05"),
        negative_threshold=Decimal("-0.05"),
    )

    assert dataset.rows
    assert all(
        row.label is DirectionLabel.BULLISH
        for row in dataset.rows
    )


def test_builder_labels_negative_growth_as_bearish() -> None:
    series = make_series(
        candle_count=30,
        daily_growth=Decimal("-0.02"),
    )

    dataset = PredictionDatasetBuilder().build(
        series,
        horizon=PredictionHorizon.FIVE_SESSIONS,
        positive_threshold=Decimal("0.05"),
        negative_threshold=Decimal("-0.05"),
    )

    assert dataset.rows
    assert all(
        row.label is DirectionLabel.BEARISH
        for row in dataset.rows
    )


def test_builder_uses_only_past_volume_for_ratio() -> None:
    series = make_series(candle_count=30)

    dataset = PredictionDatasetBuilder().build(
        series,
        horizon=PredictionHorizon.NEXT_SESSION,
        positive_threshold=Decimal("0.01"),
        negative_threshold=Decimal("-0.01"),
    )

    first_row = dataset.rows[0]

    expected_average = (
        Decimal(
            sum(
                candle.volume
                for candle in series.candles[0:20]
            )
        )
        / Decimal("20")
    )

    expected_ratio = (
        Decimal(series.candles[20].volume)
        / expected_average
    )

    assert first_row.volume_ratio_20 == expected_ratio


def test_latest_input_uses_final_candle() -> None:
    series = make_series(candle_count=30)

    latest = PredictionDatasetBuilder().build_latest_input(
        series,
        horizon=PredictionHorizon.FIVE_SESSIONS,
    )

    assert latest.as_of == series.candles[-1].timestamp
    assert latest.close_price == series.candles[-1].close_price


def test_latest_input_does_not_require_future_candle() -> None:
    series = make_series(candle_count=21)

    latest = PredictionDatasetBuilder().build_latest_input(
        series,
        horizon=PredictionHorizon.TWENTY_SESSIONS,
    )

    assert latest.as_of == series.candles[-1].timestamp
    assert not hasattr(latest, "future_return")
    assert not hasattr(latest, "label")


def test_latest_input_rejects_insufficient_history() -> None:
    series = make_series(candle_count=20)

    with pytest.raises(
        ValueError,
        match="at least 21 candles",
    ):
        PredictionDatasetBuilder().build_latest_input(
            series,
            horizon=PredictionHorizon.NEXT_SESSION,
        )
