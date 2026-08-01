"""Domain entities for probability-based stock predictions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import IntEnum, StrEnum


class PredictionHorizon(IntEnum):
    """Number of future trading sessions used for the target."""

    NEXT_SESSION = 1
    FIVE_SESSIONS = 5
    TWENTY_SESSIONS = 20


class DirectionLabel(StrEnum):
    """Observed future direction for a labelled training row."""

    BEARISH = "bearish"
    NEUTRAL = "neutral"
    BULLISH = "bullish"


@dataclass(frozen=True, slots=True)
class PredictionFeatureRow:
    """One leakage-safe model feature row.

    All features must be calculated using candles available at or before
    `as_of`. `future_return` and `label` are training-only outcomes and
    must never be used as model inputs.
    """

    display_symbol: str
    as_of: datetime
    horizon: PredictionHorizon

    close_price: Decimal
    return_1: Decimal | None
    return_5: Decimal | None
    return_20: Decimal | None

    sma_ratio_5: Decimal | None
    sma_ratio_20: Decimal | None

    volatility_5: Decimal | None
    volatility_20: Decimal | None

    volume_ratio_20: Decimal | None
    candle_body_ratio: Decimal | None
    range_ratio: Decimal | None

    future_return: Decimal
    label: DirectionLabel

    def __post_init__(self) -> None:
        if not self.display_symbol.strip():
            raise ValueError("display_symbol must not be empty")

        if self.as_of.tzinfo is None:
            raise ValueError("as_of must be timezone-aware")

        if self.close_price <= 0:
            raise ValueError("close_price must be positive")


@dataclass(frozen=True, slots=True)
class PredictionDataset:
    """Chronologically ordered training rows for one stock and horizon."""

    display_symbol: str
    horizon: PredictionHorizon
    rows: tuple[PredictionFeatureRow, ...]

    positive_threshold: Decimal
    negative_threshold: Decimal

    def __post_init__(self) -> None:
        if not self.display_symbol.strip():
            raise ValueError("display_symbol must not be empty")

        if self.positive_threshold <= 0:
            raise ValueError("positive_threshold must be positive")

        if self.negative_threshold >= 0:
            raise ValueError("negative_threshold must be negative")

        previous_timestamp: datetime | None = None

        for row in self.rows:
            if row.display_symbol != self.display_symbol:
                raise ValueError(
                    "all rows must belong to dataset display_symbol"
                )

            if row.horizon is not self.horizon:
                raise ValueError(
                    "all rows must use the dataset horizon"
                )

            if (
                previous_timestamp is not None
                and row.as_of <= previous_timestamp
            ):
                raise ValueError(
                    "dataset rows must be strictly chronological"
                )

            previous_timestamp = row.as_of
