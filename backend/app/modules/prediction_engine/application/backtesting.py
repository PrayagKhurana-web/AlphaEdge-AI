"""Leakage-safe expanding-window walk-forward validation.

Standard train/test splits evaluate a model once, on a single holdout
window. That tells you nothing about how the model would have performed
if it had been retrained repeatedly over time, and a single lucky (or
unlucky) holdout period can badly misrepresent real-world performance.

Walk-forward validation instead simulates deploying and periodically
retraining the model in production: for each fold, a model is trained
only on rows that occurred strictly before the fold's testing rows, then
evaluated on the next chronological block of unseen rows. The training
window *expands* on every fold (it always starts at row 0 and grows to
include every row seen so far), which mirrors how a real system would
accumulate more history over time rather than discarding old data.

This is what "leakage-safe" means here specifically: no fold's model
is ever trained on a row whose timestamp is later than any row it is
evaluated against. That guarantee is enforced twice, independently:

  1. PredictionDataset itself only accepts strictly chronological rows
     (domain/entities.py), so index order and time order always agree.
  2. Every fold's train/test rows are wrapped in a
     ChronologicalDatasetSplit (application/modeling.py), which asserts
     `training_rows[-1].as_of < testing_rows[0].as_of` at construction
     time -- an independent, redundant check on top of (1).

No row is ever shuffled, and no fold trains on a row it will later be
tested against.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    confusion_matrix as sk_confusion_matrix,
    precision_recall_fscore_support,
)

from app.modules.prediction_engine.application.modeling import (
    BaselineDirectionModel,
    ChronologicalDatasetSplit,
)
from app.modules.prediction_engine.domain.entities import (
    DirectionLabel,
    PredictionDataset,
    PredictionFeatureRow,
)

# Fixed reporting order for every per-class metric and the confusion
# matrix, regardless of which classes happen to appear in any given
# fold. Kept as a module-level constant, mirroring modeling.py's
# FEATURE_NAMES pattern, so the order is defined exactly once.
CLASS_ORDER: tuple[DirectionLabel, ...] = (
    DirectionLabel.BEARISH,
    DirectionLabel.NEUTRAL,
    DirectionLabel.BULLISH,
)

_CLASS_ORDER_VALUES: tuple[str, ...] = tuple(
    label.value for label in CLASS_ORDER
)


def _require_unit_interval(value: Decimal, field_name: str) -> None:
    """Raise ValueError unless `value` is within the closed range [0, 1]."""
    if not (Decimal("0") <= value <= Decimal("1")):
        raise ValueError(f"{field_name} must be between 0 and 1, got {value!r}")


@dataclass(frozen=True, slots=True)
class WalkForwardFold:
    """One expanding-window fold's boundaries and out-of-sample metrics.

    `training_end` is guaranteed to be strictly earlier than
    `testing_start`: the model that produced this fold's metrics never
    saw any row at or after `testing_start` during training.
    """

    fold_number: int
    training_start: datetime
    training_end: datetime
    testing_start: datetime
    testing_end: datetime
    training_row_count: int
    testing_row_count: int
    accuracy: Decimal
    balanced_accuracy: Decimal

    def __post_init__(self) -> None:
        if self.fold_number < 1:
            raise ValueError("fold_number must be at least 1")

        if self.training_row_count < 1:
            raise ValueError("training_row_count must be at least 1")

        if self.testing_row_count < 1:
            raise ValueError("testing_row_count must be at least 1")

        if self.training_end >= self.testing_start:
            raise ValueError(
                "training_end must be strictly before testing_start "
                "-- a fold must never train on a row at or after its "
                "own testing period"
            )

        _require_unit_interval(self.accuracy, "accuracy")
        _require_unit_interval(self.balanced_accuracy, "balanced_accuracy")


@dataclass(frozen=True, slots=True)
class WalkForwardSummary:
    """Aggregated out-of-sample results across every walk-forward fold.

    All metrics here are computed over the pooled out-of-sample
    predictions from every fold -- each row contributes exactly once,
    using the prediction made by the fold whose model had never seen
    that row during training.
    """

    folds: tuple[WalkForwardFold, ...]
    total_predictions: int

    accuracy: Decimal
    balanced_accuracy: Decimal

    bearish_precision: Decimal
    bearish_recall: Decimal
    bearish_f1: Decimal

    neutral_precision: Decimal
    neutral_recall: Decimal
    neutral_f1: Decimal

    bullish_precision: Decimal
    bullish_recall: Decimal
    bullish_f1: Decimal

    confusion_matrix: tuple[tuple[int, ...], ...]
    class_order: tuple[DirectionLabel, ...]

    def __post_init__(self) -> None:
        if not self.folds:
            raise ValueError("folds must not be empty")

        if self.total_predictions < 1:
            raise ValueError("total_predictions must be at least 1")

        if len(self.class_order) != 3:
            raise ValueError("class_order must contain exactly three classes")

        if len(self.confusion_matrix) != len(self.class_order):
            raise ValueError(
                "confusion_matrix row count must match class_order size"
            )

        for row in self.confusion_matrix:
            if len(row) != len(self.class_order):
                raise ValueError(
                    "confusion_matrix must be square, matching class_order size"
                )

        for field_name, value in (
            ("accuracy", self.accuracy),
            ("balanced_accuracy", self.balanced_accuracy),
            ("bearish_precision", self.bearish_precision),
            ("bearish_recall", self.bearish_recall),
            ("bearish_f1", self.bearish_f1),
            ("neutral_precision", self.neutral_precision),
            ("neutral_recall", self.neutral_recall),
            ("neutral_f1", self.neutral_f1),
            ("bullish_precision", self.bullish_precision),
            ("bullish_recall", self.bullish_recall),
            ("bullish_f1", self.bullish_f1),
        ):
            _require_unit_interval(value, field_name)


class WalkForwardBacktester:
    """Run leakage-safe expanding-window walk-forward validation.

    Stateless, mirroring BaselineDirectionModel's and
    ChronologicalDatasetSplitter's existing style -- configuration is
    passed to `run()`, not to a constructor.
    """

    def run(
        self,
        dataset: PredictionDataset,
        *,
        minimum_training_rows: int = 60,
        testing_window_size: int = 20,
        step_size: int = 20,
    ) -> WalkForwardSummary:
        """Run expanding-window walk-forward validation over `dataset`.

        Fold construction:
            Fold 1 trains on `dataset.rows[0:minimum_training_rows]` and
            tests on the next `testing_window_size` rows. Each
            subsequent fold's training window *expands* to include every
            row up to (but not including) that fold's testing window --
            i.e. training always starts at row 0 -- and the testing
            window advances by `step_size` rows each fold. The final
            fold may contain fewer than `testing_window_size` testing
            rows (whatever remains), but always at least one.

        Args:
            dataset: A chronologically ordered PredictionDataset.
            minimum_training_rows: Row count used to train the first
                fold. Must be at least 2 (a model cannot usefully train
                on fewer rows, and this dataclass requires at least two
                label classes to be present within them regardless).
            testing_window_size: Number of rows evaluated per fold
                (except possibly the last). Must be at least 1.
            step_size: Number of rows the testing window advances by
                between folds. Must be at least 1. Independent of
                `testing_window_size` -- equal values (the default)
                produce contiguous, non-overlapping testing windows that
                partition the dataset exactly.

        Returns:
            A WalkForwardSummary aggregating every fold's out-of-sample
            predictions into overall and per-class metrics.

        Raises:
            ValueError: if `minimum_training_rows` is less than 2, if
                `testing_window_size` or `step_size` is less than 1, if
                `dataset` does not contain enough rows for even one
                fold, or if any fold's training rows contain fewer than
                two distinct label classes (raised by
                BaselineDirectionModel.train(), propagated unchanged).
        """
        if minimum_training_rows < 2:
            raise ValueError("minimum_training_rows must be at least 2")

        if testing_window_size < 1:
            raise ValueError("testing_window_size must be at least 1")

        if step_size < 1:
            raise ValueError("step_size must be at least 1")

        if step_size < testing_window_size:
            raise ValueError(
                "step_size must be greater than or equal to "
                "testing_window_size to prevent overlapping test windows"
            )

        rows = dataset.rows
        total_rows = len(rows)

        if total_rows < minimum_training_rows + 1:
            raise ValueError(
                "dataset does not contain enough rows for one "
                "train/test fold"
            )

        folds: list[WalkForwardFold] = []
        all_true_labels: list[str] = []
        all_predicted_labels: list[str] = []

        test_start_index = minimum_training_rows
        fold_number = 1

        while test_start_index < total_rows:
            test_end_index = min(
                test_start_index + testing_window_size,
                total_rows,
            )

            training_rows = rows[:test_start_index]
            testing_rows = rows[test_start_index:test_end_index]

            fold, true_labels, predicted_labels = self._run_fold(
                fold_number=fold_number,
                training_rows=training_rows,
                testing_rows=testing_rows,
            )

            folds.append(fold)
            all_true_labels.extend(true_labels)
            all_predicted_labels.extend(predicted_labels)

            fold_number += 1
            test_start_index += step_size

        return self._build_summary(
            folds=tuple(folds),
            true_labels=all_true_labels,
            predicted_labels=all_predicted_labels,
        )

    def _run_fold(
        self,
        *,
        fold_number: int,
        training_rows: tuple[PredictionFeatureRow, ...],
        testing_rows: tuple[PredictionFeatureRow, ...],
    ) -> tuple[WalkForwardFold, list[str], list[str]]:
        """Train and evaluate exactly one fold.

        Reuses ChronologicalDatasetSplit for its independent chronology
        assertion, and BaselineDirectionModel for both training (which
        already validates at least two training classes are present)
        and its existing feature pipeline (which already excludes
        `future_return` and `label` from the model's inputs).

        Raises:
            ValueError: propagated unchanged from
                BaselineDirectionModel.train() if `training_rows`
                contains fewer than two distinct label classes.
        """
        split = ChronologicalDatasetSplit(
            training_rows=training_rows,
            testing_rows=testing_rows,
        )

        model = BaselineDirectionModel()
        result = model.train(split)

        # BaselineModelMetrics already gives us this fold's accuracy and
        # balanced accuracy, computed via the same reused pipeline --
        # recomputing them here would duplicate, not reuse, that logic.
        fold = WalkForwardFold(
            fold_number=fold_number,
            training_start=training_rows[0].as_of,
            training_end=training_rows[-1].as_of,
            testing_start=testing_rows[0].as_of,
            testing_end=testing_rows[-1].as_of,
            training_row_count=result.metrics.training_row_count,
            testing_row_count=result.metrics.testing_row_count,
            accuracy=result.metrics.accuracy,
            balanced_accuracy=result.metrics.balanced_accuracy,
        )

        # BaselineModelMetrics does not expose raw predictions, and
        # aggregate (pooled) metrics need every fold's individual
        # predictions -- so testing rows are vectorized again here,
        # via the same shared, private _feature_vector used inside
        # BaselineDirectionModel.train(), and predicted with the
        # already-fitted pipeline (no re-fitting).
        testing_features = [
            BaselineDirectionModel._feature_vector(row)
            for row in testing_rows
        ]
        predictions = result.pipeline.predict(testing_features)

        true_labels = [row.label.value for row in testing_rows]
        predicted_labels = [str(value) for value in predictions]

        return fold, true_labels, predicted_labels

    def _build_summary(
        self,
        *,
        folds: tuple[WalkForwardFold, ...],
        true_labels: list[str],
        predicted_labels: list[str],
    ) -> WalkForwardSummary:
        """Aggregate every fold's pooled out-of-sample predictions.

        `zero_division=0` is passed explicitly to
        precision_recall_fscore_support so that a class with no
        predicted (or no true) occurrences in the pooled results
        reports 0 rather than raising or emitting an undefined-metric
        warning.
        """
        overall_accuracy = Decimal(
            str(accuracy_score(true_labels, predicted_labels))
        )
        overall_balanced_accuracy = Decimal(
            str(balanced_accuracy_score(true_labels, predicted_labels))
        )

        precision, recall, f1, _support = precision_recall_fscore_support(
            true_labels,
            predicted_labels,
            labels=_CLASS_ORDER_VALUES,
            zero_division=0,
        )

        raw_confusion_matrix = sk_confusion_matrix(
            true_labels,
            predicted_labels,
            labels=_CLASS_ORDER_VALUES,
        )
        confusion_matrix_tuple = tuple(
            tuple(int(value) for value in row)
            for row in raw_confusion_matrix
        )

        return WalkForwardSummary(
            folds=folds,
            total_predictions=len(true_labels),
            accuracy=overall_accuracy,
            balanced_accuracy=overall_balanced_accuracy,
            bearish_precision=Decimal(str(precision[0])),
            bearish_recall=Decimal(str(recall[0])),
            bearish_f1=Decimal(str(f1[0])),
            neutral_precision=Decimal(str(precision[1])),
            neutral_recall=Decimal(str(recall[1])),
            neutral_f1=Decimal(str(f1[1])),
            bullish_precision=Decimal(str(precision[2])),
            bullish_recall=Decimal(str(recall[2])),
            bullish_f1=Decimal(str(f1[2])),
            confusion_matrix=confusion_matrix_tuple,
            class_order=CLASS_ORDER,
        )