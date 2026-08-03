from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.modules.prediction_engine.application.backtesting import (
    WalkForwardBacktester,
)
from app.modules.prediction_engine.domain.entities import (
    DirectionLabel,
    PredictionDataset,
    PredictionFeatureRow,
    PredictionHorizon,
)


START = datetime(2025, 1, 1, tzinfo=timezone.utc)

_CYCLE_LABELS = (
    DirectionLabel.BEARISH,
    DirectionLabel.NEUTRAL,
    DirectionLabel.BULLISH,
)


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


def make_dataset(row_count: int) -> PredictionDataset:
    """Round-robin cycled labels, matching test_prediction_modeling.py's
    fixture style -- any contiguous block of 3+ rows contains every
    class, so training windows of realistic size never accidentally hit
    the single-class rejection path in these general-purpose tests."""
    rows = tuple(
        make_row(index, _CYCLE_LABELS[index % len(_CYCLE_LABELS)])
        for index in range(row_count)
    )

    return PredictionDataset(
        display_symbol="RELIANCE.NSE",
        horizon=PredictionHorizon.FIVE_SESSIONS,
        rows=rows,
        positive_threshold=Decimal("0.03"),
        negative_threshold=Decimal("-0.03"),
    )


def make_single_class_prefix_dataset(
    *,
    single_class_row_count: int,
    trailing_row_count: int,
) -> PredictionDataset:
    """A dataset whose first `single_class_row_count` rows are all
    BULLISH (one class only), followed by round-robin cycled rows."""
    prefix_rows = tuple(
        make_row(index, DirectionLabel.BULLISH)
        for index in range(single_class_row_count)
    )
    trailing_rows = tuple(
        make_row(
            single_class_row_count + offset,
            _CYCLE_LABELS[offset % len(_CYCLE_LABELS)],
        )
        for offset in range(trailing_row_count)
    )

    rows = prefix_rows + trailing_rows

    return PredictionDataset(
        display_symbol="RELIANCE.NSE",
        horizon=PredictionHorizon.FIVE_SESSIONS,
        rows=rows,
        positive_threshold=Decimal("0.03"),
        negative_threshold=Decimal("-0.03"),
    )


def test_expanding_training_window() -> None:
    dataset = make_dataset(row_count=140)

    summary = WalkForwardBacktester().run(
        dataset,
        minimum_training_rows=60,
        testing_window_size=20,
        step_size=20,
    )

    training_row_counts = [
        fold.training_row_count for fold in summary.folds
    ]

    assert training_row_counts == [60, 80, 100, 120]

    for earlier, later in zip(
        training_row_counts,
        training_row_counts[1:],
    ):
        assert later > earlier


def test_strict_chronological_separation_between_train_and_test() -> None:
    dataset = make_dataset(row_count=140)

    summary = WalkForwardBacktester().run(
        dataset,
        minimum_training_rows=60,
        testing_window_size=20,
        step_size=20,
    )

    for fold in summary.folds:
        assert fold.training_end < fold.testing_start


def test_multiple_folds_are_produced() -> None:
    dataset = make_dataset(row_count=140)

    summary = WalkForwardBacktester().run(
        dataset,
        minimum_training_rows=60,
        testing_window_size=20,
        step_size=20,
    )

    assert len(summary.folds) == 4


def test_final_fold_is_a_correct_partial_window() -> None:
    # 150 rows: full windows at [60:80], [80:100], [100:120], [120:140],
    # then a final partial window [140:150] of only 10 rows.
    dataset = make_dataset(row_count=150)

    summary = WalkForwardBacktester().run(
        dataset,
        minimum_training_rows=60,
        testing_window_size=20,
        step_size=20,
    )

    assert len(summary.folds) == 5

    final_fold = summary.folds[-1]
    assert final_fold.testing_row_count == 10
    assert final_fold.testing_row_count < 20
    assert final_fold.testing_row_count >= 1

    for fold in summary.folds[:-1]:
        assert fold.testing_row_count == 20


def test_total_prediction_count_matches_folds() -> None:
    dataset = make_dataset(row_count=150)

    summary = WalkForwardBacktester().run(
        dataset,
        minimum_training_rows=60,
        testing_window_size=20,
        step_size=20,
    )

    assert summary.total_predictions == sum(
        fold.testing_row_count for fold in summary.folds
    )
    # With step_size == testing_window_size, testing windows are
    # contiguous and non-overlapping, so total predictions equal every
    # row after the first fold's training window.
    assert summary.total_predictions == 150 - 60


def test_all_metrics_are_between_zero_and_one() -> None:
    dataset = make_dataset(row_count=140)

    summary = WalkForwardBacktester().run(
        dataset,
        minimum_training_rows=60,
        testing_window_size=20,
        step_size=20,
    )

    metric_values = (
        summary.accuracy,
        summary.balanced_accuracy,
        summary.bearish_precision,
        summary.bearish_recall,
        summary.bearish_f1,
        summary.neutral_precision,
        summary.neutral_recall,
        summary.neutral_f1,
        summary.bullish_precision,
        summary.bullish_recall,
        summary.bullish_f1,
    )

    for value in metric_values:
        assert Decimal("0") <= value <= Decimal("1")

    for fold in summary.folds:
        assert Decimal("0") <= fold.accuracy <= Decimal("1")
        assert Decimal("0") <= fold.balanced_accuracy <= Decimal("1")


def test_confusion_matrix_uses_fixed_class_order() -> None:
    dataset = make_dataset(row_count=140)

    summary = WalkForwardBacktester().run(
        dataset,
        minimum_training_rows=60,
        testing_window_size=20,
        step_size=20,
    )

    assert summary.class_order == (
        DirectionLabel.BEARISH,
        DirectionLabel.NEUTRAL,
        DirectionLabel.BULLISH,
    )
    assert len(summary.confusion_matrix) == 3
    assert all(len(row) == 3 for row in summary.confusion_matrix)


def test_rejects_dataset_with_insufficient_rows() -> None:
    dataset = make_dataset(row_count=10)

    with pytest.raises(
        ValueError,
        match="does not contain enough rows",
    ):
        WalkForwardBacktester().run(
            dataset,
            minimum_training_rows=60,
            testing_window_size=20,
            step_size=20,
        )


@pytest.mark.parametrize(
    ("kwargs", "expected_match"),
    [
        ({"minimum_training_rows": 1}, "minimum_training_rows"),
        ({"testing_window_size": 0}, "testing_window_size"),
        ({"step_size": 0}, "step_size"),
    ],
)
def test_rejects_invalid_configuration(
    kwargs: dict[str, int],
    expected_match: str,
) -> None:
    dataset = make_dataset(row_count=140)

    with pytest.raises(ValueError, match=expected_match):
        WalkForwardBacktester().run(dataset, **kwargs)


def test_rejects_fold_with_single_class_training_data() -> None:
    dataset = make_single_class_prefix_dataset(
        single_class_row_count=60,
        trailing_row_count=40,
    )

    with pytest.raises(
        ValueError,
        match="at least two classes",
    ):
        WalkForwardBacktester().run(
            dataset,
            minimum_training_rows=60,
            testing_window_size=20,
            step_size=20,
        )

def test_rejects_overlapping_testing_windows() -> None:
    dataset = make_dataset(row_count=140)

    with pytest.raises(
        ValueError,
        match="prevent overlapping test windows",
    ):
        WalkForwardBacktester().run(
            dataset,
            minimum_training_rows=60,
            testing_window_size=20,
            step_size=10,
        )
