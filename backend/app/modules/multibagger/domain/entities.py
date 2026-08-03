"""Domain entities for Multibagger Potential analysis."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum


class MultibaggerPotentialCategory(StrEnum):
    """Interpretation of the final potential score."""

    VERY_HIGH = "very_high"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    VERY_LOW = "very_low"


class MultibaggerObservationType(StrEnum):
    """Tone attached to an explainable observation."""

    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


@dataclass(frozen=True, slots=True)
class MultibaggerObservation:
    """One explainable strength, neutral point, or warning."""

    category: str
    observation_type: MultibaggerObservationType
    message: str

    def __post_init__(self) -> None:
        if not self.category.strip():
            raise ValueError("category must not be empty")

        if not self.message.strip():
            raise ValueError("message must not be empty")


@dataclass(frozen=True, slots=True)
class MultibaggerPotentialSnapshot:
    """Deterministic long-term stock-potential assessment."""

    symbol: str
    display_symbol: str
    company_name: str

    potential_score: int
    potential_category: MultibaggerPotentialCategory

    growth_quality_score: int
    financial_strength_score: int
    valuation_attractiveness_score: int
    momentum_score: int
    risk_quality_score: int

    data_completeness_score: int

    market_cap: Decimal | None
    revenue_growth: Decimal | None
    earnings_growth: Decimal | None
    return_on_equity: Decimal | None
    debt_to_equity: Decimal | None
    trailing_pe: Decimal | None
    price_to_book: Decimal | None

    observations: tuple[MultibaggerObservation, ...]
    calculated_at: datetime

    methodology_version: str = "multibagger-rules-v1"

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("symbol must not be empty")

        if not self.display_symbol.strip():
            raise ValueError("display_symbol must not be empty")

        if not self.company_name.strip():
            raise ValueError("company_name must not be empty")

        for name, value in (
            ("potential_score", self.potential_score),
            ("growth_quality_score", self.growth_quality_score),
            ("financial_strength_score", self.financial_strength_score),
            (
                "valuation_attractiveness_score",
                self.valuation_attractiveness_score,
            ),
            ("momentum_score", self.momentum_score),
            ("risk_quality_score", self.risk_quality_score),
            (
                "data_completeness_score",
                self.data_completeness_score,
            ),
        ):
            if not 0 <= value <= 100:
                raise ValueError(
                    f"{name} must be between 0 and 100"
                )

        if self.calculated_at.tzinfo is None:
            raise ValueError(
                "calculated_at must be timezone-aware"
            )

        if not self.observations:
            raise ValueError(
                "at least one observation is required"
            )

        if not self.methodology_version.strip():
            raise ValueError(
                "methodology_version must not be empty"
            )
