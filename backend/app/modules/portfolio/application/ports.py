from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal

from app.modules.portfolio.domain.entities import PortfolioHolding


class PortfolioRepository(ABC):
    """Persistence contract for portfolio holdings."""

    @abstractmethod
    async def list_for_user(
        self,
        user_id: int,
    ) -> list[PortfolioHolding]:
        """Return all holdings belonging to a user."""

    @abstractmethod
    async def get_by_symbol(
        self,
        user_id: int,
        display_symbol: str,
    ) -> PortfolioHolding | None:
        """Return one holding, or None when it does not exist."""

    @abstractmethod
    async def add(
        self,
        user_id: int,
        display_symbol: str,
        exchange: str,
        quantity: Decimal,
        average_buy_price: Decimal,
    ) -> PortfolioHolding:
        """Create and return one holding."""

    @abstractmethod
    async def update(
        self,
        user_id: int,
        display_symbol: str,
        quantity: Decimal,
        average_buy_price: Decimal,
    ) -> PortfolioHolding:
        """Update quantity and average buy price."""

    @abstractmethod
    async def delete(
        self,
        user_id: int,
        display_symbol: str,
    ) -> None:
        """Delete one holding."""
