"""Baseline chronological model training for AlphaEdge Pulse."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from app.modules.prediction_engine.domain.entities import (
    DirectionLabel,
    PredictionDataset,
    PredictionFeatureRow,
    PredictionInputRow,
)


FEATURE_NAMES: tuple[str, ...] = (
    "return_1",
    "return_5",
    "return_20",
    "sma_ratio_5",
    "sma_ratio_20",
    "volatility_5",
    "volatility_20",
    "volume_ratio_20",
    "candle_body_ratio",
    "range_ratio",
)


@dataclass(frozen=True, slots=True)
class ChronologicalDatasetSplit:
    """Chronological model-development split."""

    training_rows: tuple[PredictionFeatureRow, ...]
    testing_rows: tuple[PredictionFeatureRow, ...]

    def __post_init__(self) -> None:
        if not self.training_rows:
            raise ValueError("training_rows must not be empty")

        if not self.testing_rows:
            raise ValueError("testing_rows must not be empty")

        if (
            self.training_rows[-1].as_of
            >= self.testing_rows[0].as_of
        ):
            raise ValueError(
                "training rows must occur before testing rows"
            )


@dataclass(frozen=True, slots=True)
class BaselineModelMetrics:
    """Evaluation results from the chronological holdout period."""

    training_row_count: int
    testing_row_count: int
    accuracy: Decimal
    balanced_accuracy: Decimal


@dataclass(frozen=True, slots=True)
class DirectionProbability:
    """Probability assigned to each direction class."""

    bearish: Decimal
    neutral: Decimal
    bullish: Decimal

    def __post_init__(self) -> None:
        total = self.bearish + self.neutral + self.bullish

        if abs(total - Decimal("1")) > Decimal("0.000001"):
            raise ValueError(
                "direction probabilities must total 1"
            )


@dataclass(frozen=True, slots=True)
class BaselineTrainingResult:
    """Trained baseline pipeline and evaluation metrics."""

    pipeline: Pipeline
    metrics: BaselineModelMetrics
    classes: tuple[DirectionLabel, ...]


class ChronologicalDatasetSplitter:
    """Split prediction rows without shuffling future observations."""

    def split(
        self,
        dataset: PredictionDataset,
        *,
        training_fraction: Decimal = Decimal("0.80"),
        minimum_training_rows: int = 30,
        minimum_testing_rows: int = 5,
    ) -> ChronologicalDatasetSplit:
        if not Decimal("0") < training_fraction < Decimal("1"):
            raise ValueError(
                "training_fraction must be between 0 and 1"
            )

        total_rows = len(dataset.rows)

        if (
            total_rows
            < minimum_training_rows + minimum_testing_rows
        ):
            raise ValueError(
                "prediction dataset does not contain enough rows"
            )

        split_index = int(
            Decimal(total_rows) * training_fraction
        )

        split_index = max(
            minimum_training_rows,
            split_index,
        )

        split_index = min(
            split_index,
            total_rows - minimum_testing_rows,
        )

        return ChronologicalDatasetSplit(
            training_rows=dataset.rows[:split_index],
            testing_rows=dataset.rows[split_index:],
        )


class BaselineDirectionModel:
    """Train and evaluate a multinomial logistic-regression model."""

    def train(
        self,
        split: ChronologicalDatasetSplit,
    ) -> BaselineTrainingResult:
        training_features = [
            self._feature_vector(row)
            for row in split.training_rows
        ]
        testing_features = [
            self._feature_vector(row)
            for row in split.testing_rows
        ]

        training_labels = [
            row.label.value
            for row in split.training_rows
        ]
        testing_labels = [
            row.label.value
            for row in split.testing_rows
        ]

        unique_training_classes = set(training_labels)

        if len(unique_training_classes) < 2:
            raise ValueError(
                "training data must contain at least two classes"
            )

        pipeline = Pipeline(
            steps=[
                ("scaler", StandardScaler()),
                (
                    "classifier",
                    LogisticRegression(
                        max_iter=2_000,
                        class_weight="balanced",
                        random_state=42,
                    ),
                ),
            ]
        )

        pipeline.fit(
            training_features,
            training_labels,
        )

        predictions = pipeline.predict(
            testing_features
        )

        metrics = BaselineModelMetrics(
            training_row_count=len(split.training_rows),
            testing_row_count=len(split.testing_rows),
            accuracy=Decimal(
                str(
                    accuracy_score(
                        testing_labels,
                        predictions,
                    )
                )
            ),
            balanced_accuracy=Decimal(
                str(
                    balanced_accuracy_score(
                        testing_labels,
                        predictions,
                    )
                )
            ),
        )

        classifier = pipeline.named_steps["classifier"]

        classes = tuple(
            DirectionLabel(class_name)
            for class_name in classifier.classes_
        )

        return BaselineTrainingResult(
            pipeline=pipeline,
            metrics=metrics,
            classes=classes,
        )

    def predict_probability(
        self,
        result: BaselineTrainingResult,
        row: PredictionFeatureRow | PredictionInputRow,
    ) -> DirectionProbability:
        raw_probabilities = result.pipeline.predict_proba(
            [self._feature_vector(row)]
        )[0]

        mapped = {
            DirectionLabel(class_name): Decimal(
                str(probability)
            )
            for class_name, probability in zip(
                result.pipeline.named_steps[
                    "classifier"
                ].classes_,
                raw_probabilities,
                strict=True,
            )
        }

        bearish = mapped.get(
            DirectionLabel.BEARISH,
            Decimal("0"),
        )
        neutral = mapped.get(
            DirectionLabel.NEUTRAL,
            Decimal("0"),
        )
        bullish = mapped.get(
            DirectionLabel.BULLISH,
            Decimal("0"),
        )

        total = bearish + neutral + bullish

        if total == 0:
            raise ValueError(
                "model returned zero total probability"
            )

        return DirectionProbability(
            bearish=bearish / total,
            neutral=neutral / total,
            bullish=bullish / total,
        )

    @staticmethod
    def _feature_vector(
        row: PredictionFeatureRow | PredictionInputRow,
    ) -> list[float]:
        values = [
            getattr(row, feature_name)
            for feature_name in FEATURE_NAMES
        ]

        # Missing indicator values remain neutral rather than causing
        # the baseline model to fail. A later model version can add
        # explicit missing-value indicators.
        return [
            float(value) if value is not None else 0.0
            for value in values
        ]
