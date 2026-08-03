"""HTTP routes for AlphaEdge Pulse predictions."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, status

from app.modules.prediction_engine.api.dependencies import (
    StockDirectionPredictionServiceDependency,
)
from app.modules.prediction_engine.api.schemas import (
    StockDirectionPredictionResponse,
)
from app.modules.prediction_engine.application.prediction_service import (
    PredictionRequestConfig,
)
from app.modules.prediction_engine.domain.entities import (
    PredictionHorizon,
)
from app.modules.stock_history.api.dependencies import (
    HistoricalDataServiceDependency,
)
from app.modules.stock_history.domain.exceptions import (
    HistoryProviderRateLimitedError,
    HistoryProviderTimeoutError,
    HistoryProviderUnavailableError,
    InvalidHistoricalDataError,
    InvalidHistoryRequestError,
)


router = APIRouter(
    prefix="/api/v1/predictions",
    tags=["AlphaEdge Pulse"],
)


@router.get(
    "/{display_symbol}",
    response_model=StockDirectionPredictionResponse,
    summary="Predict a stock's probable future direction",
    description=(
        "Builds a leakage-safe historical dataset, trains a baseline "
        "logistic-regression model, evaluates it chronologically and "
        "returns bearish, neutral and bullish probabilities. The "
        "result is experimental and is not a guarantee."
    ),
)
async def get_stock_direction_prediction(
    historical_service: HistoricalDataServiceDependency,
    prediction_service: StockDirectionPredictionServiceDependency,
    display_symbol: Annotated[
        str,
        Path(
            description=(
                "Stock symbol in SYMBOL.EXCHANGE format, such as "
                "RELIANCE.NSE."
            ),
        ),
    ],
    horizon: Annotated[
        PredictionHorizon,
        Query(
            description=(
                "Prediction horizon in trading sessions: 1, 5 or 20."
            ),
        ),
    ] = PredictionHorizon.FIVE_SESSIONS,
    positive_threshold: Annotated[
        Decimal,
        Query(
            alias="positiveThreshold",
            gt=Decimal("0"),
            description=(
                "Future return at or above this value is bullish."
            ),
        ),
    ] = Decimal("0.03"),
    negative_threshold: Annotated[
        Decimal,
        Query(
            alias="negativeThreshold",
            lt=Decimal("0"),
            description=(
                "Future return at or below this value is bearish."
            ),
        ),
    ] = Decimal("-0.03"),
    period: Annotated[
        str,
        Query(
            description=(
                "Historical lookback period used for model training."
            ),
        ),
    ] = "5y",
    interval: Annotated[
        str,
        Query(
            description="Historical candle interval.",
        ),
    ] = "1d",
) -> StockDirectionPredictionResponse:
    try:
        historical_series = await historical_service.get_history(
            display_symbol,
            period=period,
            interval=interval,
        )

        config = PredictionRequestConfig(
            horizon=horizon,
            positive_threshold=positive_threshold,
            negative_threshold=negative_threshold,
        )

        prediction = prediction_service.predict(
            historical_series,
            config=config,
        )

    except InvalidHistoryRequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_PREDICTION_HISTORY_REQUEST",
                "message": str(exc),
            },
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": "PREDICTION_DATA_INSUFFICIENT",
                "message": str(exc),
            },
        ) from exc

    except HistoryProviderRateLimitedError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "HISTORY_PROVIDER_RATE_LIMITED",
                "message": (
                    "Historical market data is temporarily "
                    "rate-limited."
                ),
            },
        ) from exc

    except HistoryProviderTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail={
                "code": "HISTORY_PROVIDER_TIMEOUT",
                "message": (
                    "Historical market data did not respond in time."
                ),
            },
        ) from exc

    except (
        HistoryProviderUnavailableError,
        InvalidHistoricalDataError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "PREDICTION_DATA_UNAVAILABLE",
                "message": (
                    "Reliable historical data is currently "
                    "unavailable for this prediction."
                ),
            },
        ) from exc

    return StockDirectionPredictionResponse.from_domain(
        prediction
    )
