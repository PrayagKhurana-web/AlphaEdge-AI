from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.modules.prediction_engine.domain.entities import (
    DirectionLabel,
    PredictionDataset,
    PredictionFeatureRow,
    PredictionHorizon,
)


NOW = datetime(2026, 8, 1, tzinfo=timezone.utc)


def make_row(
    *,
    as_of: datetime = NOW,
    display_symbol: str = "RELIANCE.NSE",
    horizon: PredictionHorizon = PredictionHorizon.FIVE_SESSIONS,
) -> PredictionFeatureRow:
    return PredictionFeatureRow(
        display_symbol=display_symbol,
        as_of=as_of,
        horizon=horizon,
        close_price=Decimal("100"),
        return_1=Decimal("0.01"),
        return_5=Decimal("0.03"),
        return_20=Decimal("0.08"),
        sma_ratio_5=Decimal("1.02"),
        sma_ratio_20=Decimal("1.05"),
        volatility_5=Decimal("0.02"),
        volatility_20=Decimal("0.04"),
        volume_ratio_20=Decimal("1.30"),
        candle_body_ratio=Decimal("0.40"),
        range_ratio=Decimal("0.03"),
        future_return=Decimal("0.06"),
        label=DirectionLabel.BULLISH,
    )


def test_feature_row_accepts_valid_values() -> None:
    row = make_row()

    assert row.display_symbol == "RELIANCE.NSE"
    assert row.horizon is PredictionHorizon.FIVE_SESSIONS
    assert row.label is DirectionLabel.BULLISH


def test_feature_row_rejects_naive_timestamp() -> None:
    with pytest.raises(
        ValueError,
        match="as_of must be timezone-aware",
    ):
        make_row(as_of=datetime(2026, 8, 1))


def test_dataset_requires_chronological_rows() -> None:
    later = make_row(as_of=NOW + timedelta(days=1))
    earlier = make_row(as_of=NOW)

    with pytest.raises(
        ValueError,
        match="strictly chronological",
    ):
        PredictionDataset(
            display_symbol="RELIANCE.NSE",
            horizon=PredictionHorizon.FIVE_SESSIONS,
            rows=(later, earlier),
            positive_threshold=Decimal("0.03"),
            negative_threshold=Decimal("-0.03"),
        )


def test_dataset_rejects_wrong_symbol() -> None:
    row = make_row(display_symbol="TCS.NSE")

    with pytest.raises(
        ValueError,
        match="dataset display_symbol",
    ):
        PredictionDataset(
            display_symbol="RELIANCE.NSE",
            horizon=PredictionHorizon.FIVE_SESSIONS,
            rows=(row,),
            positive_threshold=Decimal("0.03"),
            negative_threshold=Decimal("-0.03"),
        )
