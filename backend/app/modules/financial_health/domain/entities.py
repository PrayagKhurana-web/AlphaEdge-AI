"""Domain entities for the financial_health module."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from app.modules.financial_statements.domain.entities import (
    FinancialStatementPeriod,
)
from app.modules.stock_search.domain.entities import StockExchange


class FinancialHealthRating(StrEnum):
    """Overall deterministic financial-health rating."""

    STRONG = "strong"
    HEALTHY = "healthy"
    MIXED = "mixed"
    WEAK = "weak"
    HIGH_RISK = "high_risk"


class FinancialHealthObservationType(StrEnum):
    """Tone assigned to one financial-health observation."""

    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


@dataclass(frozen=True, slots=True)
class FinancialHealthObservation:
    """One rule-based strength, neutral point, or risk."""

    category: str
    observation_type: FinancialHealthObservationType
    message: str


@dataclass(frozen=True, slots=True)
class FinancialHealthSnapshot:
    """Deterministic financial-health assessment for a company."""

    symbol: str
    display_symbol: str
    company_name: str
    exchange: StockExchange
    period: FinancialStatementPeriod
    currency: str | None

    overall_score: int
    rating: FinancialHealthRating

    growth_score: int
    profitability_score: int
    balance_sheet_score: int
    cash_flow_score: int

    revenue_growth: Decimal | None
    net_income_growth: Decimal | None
    ebitda_margin: Decimal | None
    net_profit_margin: Decimal | None
    debt_to_equity: Decimal | None
    operating_cash_flow_growth: Decimal | None
    free_cash_flow_growth: Decimal | None
    cash_conversion_ratio: Decimal | None

    observations: tuple[FinancialHealthObservation, ...]
    calculated_at: datetime
