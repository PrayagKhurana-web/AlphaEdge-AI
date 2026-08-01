from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.modules.prediction_engine.application.modeling import (
    ChronologicalDatasetSplit,
    DirectionProbability,
)
from app.modules.prediction_engine.application.prediction_service import (
    PredictionRequestConfig,
    StockDirectionPredictionService,
)
from app.modules.prediction_engine.domain.entities import (
    DirectionLabel,
    PredictionDataset,
    PredictionFeatureRow,
    PredictionHorizon,
    PredictionInputRow,
)
from app.modules.stock_history.domain.entities import (
    HistoricalCandle,
    HistoricalSeries,
)
from app.modules.stock_search.domain.entities import StockExchange


START = datetime(2025, 1, 1, tzinfo=timezone.utc)


def make_feature_row(
    index: int,
) -> PredictionFeatureRow:
    labels = (
        DirectionLabel.BEARISH,
        DirectionLabel.NEUTRAL,
        DirectionLabel.BULLISH,
    )

    label = labels[index % 3]

    value = {
        DirectionLabel.BEARISH: Decimal("-0.04"),
        DirectionLabel.NEUTRAL: Decimal("0"),
        DirectionLabel.BULLISH: Decimal("0.04"),
    }[label]

    return PredictionFeatureRow(
        display_symbol="RELIANCE.NSE",
        as_of=START + timedelta(days=index),
        horizon=PredictionHorizon.FIVE_SESSIONS,
        close_price=Decimal("100") + index,
        return_1=value,
        return_5=value,
        return_20=value,
        sma_ratio_5=Decimal("1") + value,
        sma_ratio_20=Decimal("1") + value,
        volatility_5=Decimal("0.02"),
        volatility_20=Decimal("0.04"),
        volume_ratio_20=Decimal("1"),
        candle_body_ratio=Decimal("0.40"),
        range_ratio=Decimal("0.03"),
        future_return=value,
        label=label,
    )


DATASET = PredictionDataset(
    display_symbol="RELIANCE.NSE",
    horizon=PredictionHorizon.FIVE_SESSIONS,
    rows=tuple(
        make_feature_row(index)
        for index in range(80)
    ),
    positive_threshold=Decimal("0.03"),
    negative_threshold=Decimal("-0.03"),
)

LATEST_INPUT = PredictionInputRow(
    display_symbol="RELIANCE.NSE",
    as_of=START + timedelta(days=100),
    horizon=PredictionHorizon.FIVE_SESSIONS,
    close_price=Decimal("250"),
    return_1=Decimal("0.01"),
    return_5=Decimal("0.03"),
    return_20=Decimal("0.08"),
    sma_ratio_5=Decimal("1.02"),
    sma_ratio_20=Decimal("1.05"),
    volatility_5=Decimal("0.02"),
    volatility_20=Decimal("0.04"),
    volume_ratio_20=Decimal("1.20"),
    candle_body_ratio=Decimal("0.40"),
    range_ratio=Decimal("0.03"),
)


class StubBuilder:
    def build(self, *args, **kwargs):
        return DATASET

    def build_latest_input(self, *args, **kwargs):
        return LATEST_INPUT


class StubSplitter:
    def split(self, dataset, **kwargs):
        return ChronologicalDatasetSplit(
            training_rows=dataset.rows[:60],
            testing_rows=dataset.rows[60:],
        )


class StubModel:
    def train(self, split):
        return SimpleNamespace(
            metrics=SimpleNamespace(
                training_row_count=len(
                    split.training_rows
                ),
                testing_row_count=len(
                    split.testing_rows
                ),
                accuracy=Decimal("0.70"),
                balanced_accuracy=Decimal("0.68"),
            )
        )

    def predict_probability(self, result, row):
        return DirectionProbability(
            bearish=Decimal("0.20"),
            neutral=Decimal("0.25"),
            bullish=Decimal("0.55"),
        )


class StubBacktester:
    def run(self, dataset, **kwargs):
        return SimpleNamespace(
            folds=(object(), object()),
            total_predictions=40,
            accuracy=Decimal("0.65"),
            balanced_accuracy=Decimal("0.63"),
        )


def make_series() -> HistoricalSeries:
    candles = tuple(
        HistoricalCandle(
            timestamp=START + timedelta(days=index),
            open_price=Decimal("100"),
            high_price=Decimal("102"),
            low_price=Decimal("99"),
            close_price=Decimal("101"),
            adjusted_close=Decimal("101"),
            volume=1_000,
        )
        for index in range(21)
    )

    return HistoricalSeries(
        symbol="RELIANCE",
        display_symbol="RELIANCE.NSE",
        company_name="Reliance Industries",
        exchange=StockExchange.NSE,
        interval="1d",
        period="1y",
        candles=candles,
        fetched_at=START + timedelta(days=22),
    )


def make_service() -> StockDirectionPredictionService:
    return StockDirectionPredictionService(
        dataset_builder=StubBuilder(),
        splitter=StubSplitter(),
        model=StubModel(),
        backtester=StubBacktester(),
    )


def make_config() -> PredictionRequestConfig:
    return PredictionRequestConfig(
        horizon=PredictionHorizon.FIVE_SESSIONS,
        positive_threshold=Decimal("0.03"),
        negative_threshold=Decimal("-0.03"),
    )


def test_service_returns_probabilities_totalling_one() -> None:
    result = make_service().predict(
        make_series(),
        config=make_config(),
    )

    assert (
        result.bearish_probability
        + result.neutral_probability
        + result.bullish_probability
    ) == Decimal("1")


def test_service_selects_largest_probability() -> None:
    result = make_service().predict(
        make_series(),
        config=make_config(),
    )

    assert (
        result.predicted_direction
        is DirectionLabel.BULLISH
    )
    assert result.confidence_score == 55


def test_service_includes_evaluation_metrics() -> None:
    result = make_service().predict(
        make_series(),
        config=make_config(),
    )

    assert result.evaluation.training_row_count == 60
    assert result.evaluation.testing_row_count == 20
    assert (
        result.evaluation.holdout_accuracy
        == Decimal("0.70")
    )
    assert (
        result.evaluation.walk_forward_fold_count
        == 2
    )
    assert (
        result.evaluation.walk_forward_total_predictions
        == 40
    )


def test_service_returns_model_metadata() -> None:
    result = make_service().predict(
        make_series(),
        config=make_config(),
    )

    assert result.model_name == "logistic_regression"
    assert result.model_version == "pulse-baseline-v1"


def test_neutral_wins_exact_probability_tie() -> None:
    direction = (
        StockDirectionPredictionService._select_direction(
            bearish=Decimal("0.40"),
            neutral=Decimal("0.40"),
            bullish=Decimal("0.20"),
        )
    )

    assert direction is DirectionLabel.NEUTRAL


def test_bearish_wins_non_neutral_tie() -> None:
    direction = (
        StockDirectionPredictionService._select_direction(
            bearish=Decimal("0.50"),
            neutral=Decimal("0"),
            bullish=Decimal("0.50"),
        )
    )

    assert direction is DirectionLabel.BEARISH


def test_invalid_thresholds_are_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="positive_threshold",
    ):
        PredictionRequestConfig(
            horizon=PredictionHorizon.NEXT_SESSION,
            positive_threshold=Decimal("0"),
            negative_threshold=Decimal("-0.01"),
        )


def test_service_is_deterministic() -> None:
    service = make_service()
    config = make_config()
    series = make_series()

    first = service.predict(series, config=config)
    second = service.predict(series, config=config)

    assert first == second
