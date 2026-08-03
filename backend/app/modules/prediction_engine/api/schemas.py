"""API schemas for AlphaEdge Pulse predictions."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.prediction_engine.application.prediction_service import (
    PredictionModelEvaluation,
    StockDirectionPrediction,
)
from app.modules.prediction_engine.domain.entities import (
    DirectionLabel,
    PredictionHorizon,
)


class PredictionModelEvaluationResponse(BaseModel):
    """Model-quality information accompanying a prediction."""

    model_config = ConfigDict(populate_by_name=True)

    training_row_count: int = Field(alias="trainingRowCount")
    testing_row_count: int = Field(alias="testingRowCount")

    holdout_accuracy: Decimal = Field(alias="holdoutAccuracy")
    holdout_balanced_accuracy: Decimal = Field(
        alias="holdoutBalancedAccuracy"
    )

    walk_forward_fold_count: int = Field(
        alias="walkForwardFoldCount"
    )
    walk_forward_total_predictions: int = Field(
        alias="walkForwardTotalPredictions"
    )
    walk_forward_accuracy: Decimal = Field(
        alias="walkForwardAccuracy"
    )
    walk_forward_balanced_accuracy: Decimal = Field(
        alias="walkForwardBalancedAccuracy"
    )

    @classmethod
    def from_domain(
        cls,
        evaluation: PredictionModelEvaluation,
    ) -> "PredictionModelEvaluationResponse":
        return cls(
            trainingRowCount=evaluation.training_row_count,
            testingRowCount=evaluation.testing_row_count,
            holdoutAccuracy=evaluation.holdout_accuracy,
            holdoutBalancedAccuracy=(
                evaluation.holdout_balanced_accuracy
            ),
            walkForwardFoldCount=(
                evaluation.walk_forward_fold_count
            ),
            walkForwardTotalPredictions=(
                evaluation.walk_forward_total_predictions
            ),
            walkForwardAccuracy=(
                evaluation.walk_forward_accuracy
            ),
            walkForwardBalancedAccuracy=(
                evaluation.walk_forward_balanced_accuracy
            ),
        )


class StockDirectionPredictionResponse(BaseModel):
    """Public AlphaEdge Pulse prediction response."""

    model_config = ConfigDict(populate_by_name=True)

    display_symbol: str = Field(alias="displaySymbol")
    horizon: PredictionHorizon
    as_of: datetime = Field(alias="asOf")
    current_price: Decimal = Field(alias="currentPrice")

    predicted_direction: DirectionLabel = Field(
        alias="predictedDirection"
    )

    bearish_probability: Decimal = Field(
        alias="bearishProbability"
    )
    neutral_probability: Decimal = Field(
        alias="neutralProbability"
    )
    bullish_probability: Decimal = Field(
        alias="bullishProbability"
    )
    confidence_score: int = Field(alias="confidenceScore")

    positive_threshold: Decimal = Field(
        alias="positiveThreshold"
    )
    negative_threshold: Decimal = Field(
        alias="negativeThreshold"
    )

    model_name: str = Field(alias="modelName")
    model_version: str = Field(alias="modelVersion")

    evaluation: PredictionModelEvaluationResponse

    disclaimer: str = (
        "This probability-based output is experimental, is not a "
        "guarantee of future movement, and is not investment advice."
    )

    @classmethod
    def from_domain(
        cls,
        prediction: StockDirectionPrediction,
    ) -> "StockDirectionPredictionResponse":
        return cls(
            displaySymbol=prediction.display_symbol,
            horizon=prediction.horizon,
            asOf=prediction.as_of,
            currentPrice=prediction.current_price,
            predictedDirection=prediction.predicted_direction,
            bearishProbability=prediction.bearish_probability,
            neutralProbability=prediction.neutral_probability,
            bullishProbability=prediction.bullish_probability,
            confidenceScore=prediction.confidence_score,
            positiveThreshold=prediction.positive_threshold,
            negativeThreshold=prediction.negative_threshold,
            modelName=prediction.model_name,
            modelVersion=prediction.model_version,
            evaluation=(
                PredictionModelEvaluationResponse.from_domain(
                    prediction.evaluation
                )
            ),
        )
