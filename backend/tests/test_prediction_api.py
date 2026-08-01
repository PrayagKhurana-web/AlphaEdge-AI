from datetime import datetime, timezone
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.modules.prediction_engine.api.dependencies import (
    get_stock_direction_prediction_service,
)
from app.modules.prediction_engine.application.prediction_service import (
    PredictionModelEvaluation,
    StockDirectionPrediction,
)
from app.modules.prediction_engine.domain.entities import (
    DirectionLabel,
    PredictionHorizon,
)
from app.modules.stock_history.api.dependencies import (
    get_historical_data_service,
)


NOW = datetime(2026, 8, 1, tzinfo=timezone.utc)


class StubHistoricalService:
    async def get_history(
        self,
        display_symbol: str,
        *,
        period: str,
        interval: str,
    ):
        return {
            "display_symbol": display_symbol,
            "period": period,
            "interval": interval,
        }


class StubPredictionService:
    def predict(self, series, *, config):
        return StockDirectionPrediction(
            display_symbol=series["display_symbol"],
            horizon=config.horizon,
            as_of=NOW,
            current_price=Decimal("1500.50"),
            predicted_direction=DirectionLabel.BULLISH,
            bearish_probability=Decimal("0.20"),
            neutral_probability=Decimal("0.25"),
            bullish_probability=Decimal("0.55"),
            confidence_score=55,
            positive_threshold=config.positive_threshold,
            negative_threshold=config.negative_threshold,
            model_name="logistic_regression",
            model_version="pulse-baseline-v1",
            evaluation=PredictionModelEvaluation(
                training_row_count=100,
                testing_row_count=25,
                holdout_accuracy=Decimal("0.68"),
                holdout_balanced_accuracy=Decimal("0.65"),
                walk_forward_fold_count=4,
                walk_forward_total_predictions=80,
                walk_forward_accuracy=Decimal("0.64"),
                walk_forward_balanced_accuracy=Decimal("0.62"),
            ),
        )


@pytest_asyncio.fixture
async def client():
    app.dependency_overrides[
        get_historical_data_service
    ] = lambda: StubHistoricalService()

    app.dependency_overrides[
        get_stock_direction_prediction_service
    ] = lambda: StubPredictionService()

    transport = ASGITransport(app=app)

    try:
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_prediction_endpoint_returns_pulse_result(
    client: AsyncClient,
) -> None:
    response = await client.get(
        "/api/v1/predictions/RELIANCE.NSE",
        params={
            "horizon": 5,
            "positiveThreshold": "0.03",
            "negativeThreshold": "-0.03",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["displaySymbol"] == "RELIANCE.NSE"
    assert body["horizon"] == 5
    assert body["predictedDirection"] == "bullish"
    assert body["confidenceScore"] == 55
    assert body["modelName"] == "logistic_regression"
    assert body["modelVersion"] == "pulse-baseline-v1"

    assert Decimal(
        str(body["bearishProbability"])
    ) + Decimal(
        str(body["neutralProbability"])
    ) + Decimal(
        str(body["bullishProbability"])
    ) == Decimal("1")

    assert body["evaluation"]["trainingRowCount"] == 100
    assert body["evaluation"]["walkForwardFoldCount"] == 4
    assert body["disclaimer"]


@pytest.mark.asyncio
async def test_prediction_endpoint_rejects_invalid_horizon(
    client: AsyncClient,
) -> None:
    response = await client.get(
        "/api/v1/predictions/RELIANCE.NSE",
        params={"horizon": 7},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_prediction_endpoint_rejects_positive_negative_threshold(
    client: AsyncClient,
) -> None:
    response = await client.get(
        "/api/v1/predictions/RELIANCE.NSE",
        params={"negativeThreshold": "0.02"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_prediction_endpoint_uses_custom_thresholds(
    client: AsyncClient,
) -> None:
    response = await client.get(
        "/api/v1/predictions/TCS.NSE",
        params={
            "horizon": 20,
            "positiveThreshold": "0.08",
            "negativeThreshold": "-0.06",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["displaySymbol"] == "TCS.NSE"
    assert body["horizon"] == 20
    assert Decimal(
        str(body["positiveThreshold"])
    ) == Decimal("0.08")
    assert Decimal(
        str(body["negativeThreshold"])
    ) == Decimal("-0.06")
