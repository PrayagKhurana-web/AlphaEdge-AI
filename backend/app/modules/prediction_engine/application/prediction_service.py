"""Application orchestration for AlphaEdge Pulse predictions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from app.modules.prediction_engine.application.backtesting import (
    WalkForwardBacktester,
)
from app.modules.prediction_engine.application.modeling import (
    BaselineDirectionModel,
    ChronologicalDatasetSplitter,
)
from app.modules.prediction_engine.application.services import (
    PredictionDatasetBuilder,
)
from app.modules.prediction_engine.domain.entities import (
    DirectionLabel,
    PredictionHorizon,
)
from app.modules.stock_history.domain.entities import HistoricalSeries


_PROBABILITY_TOLERANCE = Decimal("0.000001")


@dataclass(frozen=True, slots=True)
class PredictionRequestConfig:
    """Configuration controlling model training and evaluation."""

    horizon: PredictionHorizon
    positive_threshold: Decimal
    negative_threshold: Decimal

    training_fraction: Decimal = Decimal("0.80")
    minimum_training_rows: int = 60
    minimum_testing_rows: int = 10
    walk_forward_testing_window: int = 20
    walk_forward_step_size: int = 20

    def __post_init__(self) -> None:
        if self.positive_threshold <= 0:
            raise ValueError(
                "positive_threshold must be positive"
            )

        if self.negative_threshold >= 0:
            raise ValueError(
                "negative_threshold must be negative"
            )

        if not (
            Decimal("0")
            < self.training_fraction
            < Decimal("1")
        ):
            raise ValueError(
                "training_fraction must be between 0 and 1"
            )

        if self.minimum_training_rows < 2:
            raise ValueError(
                "minimum_training_rows must be at least 2"
            )

        if self.minimum_testing_rows < 1:
            raise ValueError(
                "minimum_testing_rows must be at least 1"
            )

        if self.walk_forward_testing_window < 1:
            raise ValueError(
                "walk_forward_testing_window must be at least 1"
            )

        if self.walk_forward_step_size < (
            self.walk_forward_testing_window
        ):
            raise ValueError(
                "walk_forward_step_size must be greater than "
                "or equal to walk_forward_testing_window"
            )


@dataclass(frozen=True, slots=True)
class PredictionModelEvaluation:
    """Holdout and walk-forward model evaluation metrics."""

    training_row_count: int
    testing_row_count: int

    holdout_accuracy: Decimal
    holdout_balanced_accuracy: Decimal

    walk_forward_fold_count: int
    walk_forward_total_predictions: int
    walk_forward_accuracy: Decimal
    walk_forward_balanced_accuracy: Decimal

    def __post_init__(self) -> None:
        if self.training_row_count < 1:
            raise ValueError(
                "training_row_count must be positive"
            )

        if self.testing_row_count < 1:
            raise ValueError(
                "testing_row_count must be positive"
            )

        if self.walk_forward_fold_count < 1:
            raise ValueError(
                "walk_forward_fold_count must be positive"
            )

        if self.walk_forward_total_predictions < 1:
            raise ValueError(
                "walk_forward_total_predictions must be positive"
            )

        for name, value in (
            ("holdout_accuracy", self.holdout_accuracy),
            (
                "holdout_balanced_accuracy",
                self.holdout_balanced_accuracy,
            ),
            (
                "walk_forward_accuracy",
                self.walk_forward_accuracy,
            ),
            (
                "walk_forward_balanced_accuracy",
                self.walk_forward_balanced_accuracy,
            ),
        ):
            if not Decimal("0") <= value <= Decimal("1"):
                raise ValueError(
                    f"{name} must be between 0 and 1"
                )


@dataclass(frozen=True, slots=True)
class StockDirectionPrediction:
    """Probability-based AlphaEdge Pulse prediction."""

    display_symbol: str
    horizon: PredictionHorizon
    as_of: datetime
    current_price: Decimal

    predicted_direction: DirectionLabel

    bearish_probability: Decimal
    neutral_probability: Decimal
    bullish_probability: Decimal
    confidence_score: int

    positive_threshold: Decimal
    negative_threshold: Decimal

    model_name: str
    model_version: str

    evaluation: PredictionModelEvaluation

    def __post_init__(self) -> None:
        if not self.display_symbol.strip():
            raise ValueError(
                "display_symbol must not be empty"
            )

        if self.as_of.tzinfo is None:
            raise ValueError(
                "as_of must be timezone-aware"
            )

        if self.current_price <= 0:
            raise ValueError(
                "current_price must be positive"
            )

        if self.positive_threshold <= 0:
            raise ValueError(
                "positive_threshold must be positive"
            )

        if self.negative_threshold >= 0:
            raise ValueError(
                "negative_threshold must be negative"
            )

        probabilities = (
            self.bearish_probability,
            self.neutral_probability,
            self.bullish_probability,
        )

        for probability in probabilities:
            if not Decimal("0") <= probability <= Decimal("1"):
                raise ValueError(
                    "probabilities must be between 0 and 1"
                )

        total = sum(
            probabilities,
            start=Decimal("0"),
        )

        if abs(total - Decimal("1")) > _PROBABILITY_TOLERANCE:
            raise ValueError(
                "prediction probabilities must total 1"
            )

        if not 0 <= self.confidence_score <= 100:
            raise ValueError(
                "confidence_score must be between 0 and 100"
            )

        if not self.model_name.strip():
            raise ValueError(
                "model_name must not be empty"
            )

        if not self.model_version.strip():
            raise ValueError(
                "model_version must not be empty"
            )


class StockDirectionPredictionService:
    """Train, evaluate and generate an AlphaEdge Pulse prediction."""

    def __init__(
        self,
        *,
        dataset_builder: PredictionDatasetBuilder | None = None,
        splitter: ChronologicalDatasetSplitter | None = None,
        model: BaselineDirectionModel | None = None,
        backtester: WalkForwardBacktester | None = None,
    ) -> None:
        self._dataset_builder = (
            dataset_builder or PredictionDatasetBuilder()
        )
        self._splitter = (
            splitter or ChronologicalDatasetSplitter()
        )
        self._model = (
            model or BaselineDirectionModel()
        )
        self._backtester = (
            backtester or WalkForwardBacktester()
        )

    def predict(
        self,
        series: HistoricalSeries,
        *,
        config: PredictionRequestConfig,
    ) -> StockDirectionPrediction:
        """Generate one probability-based direction prediction.

        Labelled historical rows are used for model development and
        evaluation. The latest inference row contains no future return
        or observed label, preventing fabricated outcomes and future-data
        leakage.
        """

        dataset = self._dataset_builder.build(
            series,
            horizon=config.horizon,
            positive_threshold=config.positive_threshold,
            negative_threshold=config.negative_threshold,
        )

        split = self._splitter.split(
            dataset,
            training_fraction=config.training_fraction,
            minimum_training_rows=(
                config.minimum_training_rows
            ),
            minimum_testing_rows=(
                config.minimum_testing_rows
            ),
        )

        training_result = self._model.train(split)

        walk_forward = self._backtester.run(
            dataset,
            minimum_training_rows=(
                config.minimum_training_rows
            ),
            testing_window_size=(
                config.walk_forward_testing_window
            ),
            step_size=config.walk_forward_step_size,
        )

        latest_input = (
            self._dataset_builder.build_latest_input(
                series,
                horizon=config.horizon,
            )
        )

        probabilities = self._model.predict_probability(
            training_result,
            latest_input,
        )

        predicted_direction = self._select_direction(
            bearish=probabilities.bearish,
            neutral=probabilities.neutral,
            bullish=probabilities.bullish,
        )

        highest_probability = max(
            probabilities.bearish,
            probabilities.neutral,
            probabilities.bullish,
        )

        confidence_score = int(
            (
                highest_probability
                * Decimal("100")
            ).quantize(
                Decimal("1"),
                rounding=ROUND_HALF_UP,
            )
        )

        evaluation = PredictionModelEvaluation(
            training_row_count=(
                training_result.metrics.training_row_count
            ),
            testing_row_count=(
                training_result.metrics.testing_row_count
            ),
            holdout_accuracy=(
                training_result.metrics.accuracy
            ),
            holdout_balanced_accuracy=(
                training_result.metrics.balanced_accuracy
            ),
            walk_forward_fold_count=len(
                walk_forward.folds
            ),
            walk_forward_total_predictions=(
                walk_forward.total_predictions
            ),
            walk_forward_accuracy=(
                walk_forward.accuracy
            ),
            walk_forward_balanced_accuracy=(
                walk_forward.balanced_accuracy
            ),
        )

        return StockDirectionPrediction(
            display_symbol=latest_input.display_symbol,
            horizon=latest_input.horizon,
            as_of=latest_input.as_of,
            current_price=latest_input.close_price,
            predicted_direction=predicted_direction,
            bearish_probability=probabilities.bearish,
            neutral_probability=probabilities.neutral,
            bullish_probability=probabilities.bullish,
            confidence_score=confidence_score,
            positive_threshold=config.positive_threshold,
            negative_threshold=config.negative_threshold,
            model_name="logistic_regression",
            model_version="pulse-baseline-v1",
            evaluation=evaluation,
        )

    @staticmethod
    def _select_direction(
        *,
        bearish: Decimal,
        neutral: Decimal,
        bullish: Decimal,
    ) -> DirectionLabel:
        """Choose the highest probability with deterministic ties."""

        probabilities = {
            DirectionLabel.BEARISH: bearish,
            DirectionLabel.NEUTRAL: neutral,
            DirectionLabel.BULLISH: bullish,
        }

        highest = max(probabilities.values())

        tied = {
            label
            for label, value in probabilities.items()
            if value == highest
        }

        if DirectionLabel.NEUTRAL in tied:
            return DirectionLabel.NEUTRAL

        for label in (
            DirectionLabel.BEARISH,
            DirectionLabel.NEUTRAL,
            DirectionLabel.BULLISH,
        ):
            if label in tied:
                return label

        raise RuntimeError(
            "unable to select prediction direction"
        )
