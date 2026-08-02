"""Ranked Multibagger Potential domain models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.modules.multibagger.domain.entities import (
    MultibaggerPotentialSnapshot,
)


@dataclass(frozen=True, slots=True)
class MultibaggerRankingsSnapshot:
    """Ranked results from a configured screening universe."""

    rankings: tuple[MultibaggerPotentialSnapshot, ...]
    failed_symbols: tuple[str, ...]

    universe_size: int
    successful_count: int
    minimum_score: int
    result_limit: int

    generated_at: datetime
    cache_expires_at: datetime

    growth_weight: int = 30
    financial_strength_weight: int = 25
    valuation_weight: int = 15
    momentum_weight: int = 20
    risk_weight: int = 10

    def __post_init__(self) -> None:
        if self.universe_size <= 0:
            raise ValueError("universe_size must be positive")

        if not 0 <= self.successful_count <= self.universe_size:
            raise ValueError(
                "successful_count must be between zero and universe_size"
            )

        if not 0 <= self.minimum_score <= 100:
            raise ValueError(
                "minimum_score must be between zero and 100"
            )

        if self.result_limit <= 0:
            raise ValueError("result_limit must be positive")

        if self.generated_at.tzinfo is None:
            raise ValueError(
                "generated_at must be timezone-aware"
            )

        if self.cache_expires_at.tzinfo is None:
            raise ValueError(
                "cache_expires_at must be timezone-aware"
            )

        if self.cache_expires_at <= self.generated_at:
            raise ValueError(
                "cache_expires_at must be later than generated_at"
            )

        if (
            self.growth_weight
            + self.financial_strength_weight
            + self.valuation_weight
            + self.momentum_weight
            + self.risk_weight
            != 100
        ):
            raise ValueError("ranking weights must total 100")
