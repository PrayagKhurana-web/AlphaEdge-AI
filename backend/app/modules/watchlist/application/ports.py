from __future__ import annotations

from abc import ABC, abstractmethod

from app.modules.watchlist.domain.entities import WatchlistItem


class WatchlistRepository(ABC):
    """Persistence contract for watchlist operations."""

    @abstractmethod
    async def list_for_user(self, user_id: int) -> list[WatchlistItem]:
        """Return all watchlist items for a user."""

    @abstractmethod
    async def get_by_symbol(
        self,
        user_id: int,
        display_symbol: str,
    ) -> WatchlistItem | None:
        """Return one saved stock, or None when it is not saved."""

    @abstractmethod
    async def add(
        self,
        user_id: int,
        display_symbol: str,
        exchange: str,
    ) -> WatchlistItem:
        """Persist and return a new watchlist item."""

    @abstractmethod
    async def delete(
        self,
        user_id: int,
        display_symbol: str,
    ) -> None:
        """Remove a stock from a user's watchlist."""
