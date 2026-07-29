from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class PortfolioHolding:
    """One stock position owned by a user."""

    id: int
    user_id: int
    display_symbol: str
    exchange: str
    quantity: Decimal
    average_buy_price: Decimal
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class PortfolioPosition:
    """One holding enriched with its current market valuation."""

    holding: PortfolioHolding
    company_name: str
    current_price: Decimal
    invested_amount: Decimal
    current_value: Decimal
    profit_loss: Decimal
    return_percent: Decimal
    allocation_percent: Decimal


@dataclass(frozen=True, slots=True)
class PortfolioValuation:
    """Complete portfolio valuation for one user."""

    positions: list[PortfolioPosition]
    total_invested: Decimal
    total_current_value: Decimal
    total_profit_loss: Decimal
    total_return_percent: Decimal
