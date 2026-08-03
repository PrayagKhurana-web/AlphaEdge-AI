"""Dependency wiring for the prediction engine."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from app.modules.prediction_engine.application.prediction_service import (
    StockDirectionPredictionService,
)


_service = StockDirectionPredictionService()


def get_stock_direction_prediction_service(
) -> StockDirectionPredictionService:
    """Return the process-wide stateless prediction service."""

    return _service


StockDirectionPredictionServiceDependency = Annotated[
    StockDirectionPredictionService,
    Depends(get_stock_direction_prediction_service),
]
