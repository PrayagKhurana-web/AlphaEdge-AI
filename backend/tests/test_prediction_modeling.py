from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.modules.prediction_engine.application.modeling import (
    BaselineDirectionModel,
    ChronologicalDatasetSplitter,
)
from app.modules.prediction_engine.domain.entities import (
    DirectionLabel,
    PredictionDataset,
    PredictionFeatureRow,
    PredictionHorizon,
)


START = datetime(2025, 1, 1, tzinfo=timezone.utc)


def make_row(
    index: int,
    label: DirectionLabel,
) -> PredictionFeatureRow:
    direction_value = {
        DirectionLabel.BEARISH: Decimal("-0.04"),
        DirectionLabel.NEUTRAL: Decimal("0"),
        DirectionLabel.BULLISH: Decimal("0.04"),
    }[label]

    return PredictionFeatureRow(
        display_symbol="RELIANCE.NSE",
        as_of=START + timedelta(days=index),
        horizon=PredictionHorizon.FIVE_SESSIONS,
        close_price=Decimal("100") + Decimal(index),
        return_1=direction_value,
        return_5=direction_value,
        return_20=direction_value,
        sma_ratio_5=Decimal("1") + direction_value,
        sma_ratio_20=Decimal("1") + direction_value,
        volatility_5=Decimal("0.02"),
        volatility_20=Decimal("0.04"),
        volume_ratio_20=Decimal("1") + direction_value,
        candle_body_ratio=Decimal("0.40"),
        range_ratio=Decimal("0.03"),
        future_return=direction_value,
        label=label,
    )


def make_dataset(
    row_count: int = 60,
) -> PredictionDataset:
    labels = (
        DirectionLabel.BEARISH,
        DirectionLabel.NEUTRAL,
        DirectionLabel.BULLISH,
    )

    rows = tuple(
        make_row(
            index,
            labels[index % len(labels)],
        )
        for index in range(row_count)
    )

    return PredictionDataset(
        display_symbol="RELIANCE.NSE",
        horizon=PredictionHorizon.FIVE_SESSIONS,
        rows=rows,
        positive_threshold=Decimal("0.03"),
        negative_threshold=Decimal("-0.03"),
    )


def test_splitter_preserves_chronological_order() -> None:
    dataset = make_dataset()

    split = ChronologicalDatasetSplitter().split(
        dataset,
        training_fraction=Decimal("0.80"),
    )

    assert len(split.training_rows) == 48
    assert len(split.testing_rows) == 12
    assert (
        split.training_rows[-1].as_of
        < split.testing_rows[0].as_of
    )


def test_splitter_rejects_small_dataset() -> None:
    dataset = make_dataset(row_count=20)

    with pytest.raises(
        ValueError,
        match="does not contain enough rows",
    ):
        ChronologicalDatasetSplitter().split(dataset)


def test_baseline_model_trains_and_returns_metrics() -> None:
    dataset = make_dataset()

    split = ChronologicalDatasetSplitter().split(
        dataset
    )

    result = BaselineDirectionModel().train(split)

    assert result.metrics.training_row_count == 48
    assert result.metrics.testing_row_count == 12
    assert Decimal("0") <= result.metrics.accuracy <= Decimal("1")
    assert (
        Decimal("0")
        <= result.metrics.balanced_accuracy
        <= Decimal("1")
    )


def test_baseline_model_returns_probabilities() -> None:
    dataset = make_dataset()

    split = ChronologicalDatasetSplitter().split(
        dataset
    )

    model = BaselineDirectionModel()
    result = model.train(split)

    probabilities = model.predict_probability(
        result,
        split.testing_rows[0],
    )

    assert (
        probabilities.bearish
        + probabilities.neutral
        + probabilities.bullish
    ) == pytest.approx(Decimal("1"))

    assert probabilities.bearish >= 0
    assert probabilities.neutral >= 0
    assert probabilities.bullish >= 0


def test_model_rejects_single_class_training_data() -> None:
    rows = tuple(
        make_row(index, DirectionLabel.BULLISH)
        for index in range(60)
    )

    dataset = PredictionDataset(
        display_symbol="RELIANCE.NSE",
        horizon=PredictionHorizon.FIVE_SESSIONS,
        rows=rows,
        positive_threshold=Decimal("0.03"),
        negative_threshold=Decimal("-0.03"),
    )

    split = ChronologicalDatasetSplitter().split(
        dataset
    )

    with pytest.raises(
        ValueError,
        match="at least two classes",
    ):
        BaselineDirectionModel().train(split)
