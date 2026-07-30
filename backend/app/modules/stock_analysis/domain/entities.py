"""Domain entities for explainable stock outlooks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum


class StockOutlook(StrEnum):
    """Directional interpretation of the combined analysis score."""

    BULLISH = "bullish"
    NEUTRAL = "neutral"
    BEARISH = "bearish"


class StockRiskLevel(StrEnum):
    """Estimated risk derived from volatility and conflicting signals."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AnalysisReasonType(StrEnum):
    """Tone attached to one explainable analysis reason."""

    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


@dataclass(frozen=True, slots=True)
class AnalysisReason:
    """One human-readable reason contributing to the outlook."""

    category: str
    reason_type: AnalysisReasonType
    message: str


@dataclass(frozen=True, slots=True)
class StockAnalysisSnapshot:
    """Combined deterministic stock-analysis snapshot."""

    symbol: str
    display_symbol: str

    outlook: StockOutlook
    bullish_probability: int
    bearish_probability: int
    confidence_score: int
    risk_level: StockRiskLevel
    time_horizon: str

    overall_score: int
    technical_score: int
    financial_score: int
    market_activity_score: int

    current_price: Decimal
    nearest_support: Decimal | None
    nearest_resistance: Decimal | None

    reasons: tuple[AnalysisReason, ...]
    calculated_at: datetime

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("symbol must not be empty")

        if not self.display_symbol.strip():
            raise ValueError("display_symbol must not be empty")

        if self.bullish_probability + self.bearish_probability != 100:
            raise ValueError(
                "bullish_probability and bearish_probability "
                "must total 100"
            )

        for name, value in (
            ("bullish_probability", self.bullish_probability),
            ("bearish_probability", self.bearish_probability),
            ("confidence_score", self.confidence_score),
            ("overall_score", self.overall_score),
            ("technical_score", self.technical_score),
            ("financial_score", self.financial_score),
            ("market_activity_score", self.market_activity_score),
        ):
            if value < 0 or value > 100:
                raise ValueError(
                    f"{name} must be between 0 and 100"
                )

        if self.current_price <= 0:
            raise ValueError("current_price must be positive")

        if self.calculated_at.tzinfo is None:
            raise ValueError("calculated_at must be timezone-aware")

        if not self.reasons:
            raise ValueError("at least one analysis reason is required")
