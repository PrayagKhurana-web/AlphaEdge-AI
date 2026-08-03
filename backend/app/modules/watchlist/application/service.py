from __future__ import annotations

import re

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.watchlist.application.ports import WatchlistRepository
from app.modules.watchlist.domain.entities import WatchlistItem
from app.modules.watchlist.domain.exceptions import (
    WatchlistItemAlreadyExistsError,
)


_DISPLAY_SYMBOL_PATTERN = re.compile(
    r"^[A-Z0-9][A-Z0-9&\-]{0,29}\.(NSE|BSE)$"
)


class InvalidWatchlistSymbolError(ValueError):
    """Raised when a display symbol is not a supported NSE/BSE symbol."""


class WatchlistService:
    """Application service coordinating watchlist operations."""

    def __init__(
        self,
        repository: WatchlistRepository,
        session: AsyncSession,
    ) -> None:
        self._repository = repository
        self._session = session

    @staticmethod
    def normalize_display_symbol(display_symbol: str) -> str:
        normalized = display_symbol.strip().upper()

        if not _DISPLAY_SYMBOL_PATTERN.fullmatch(normalized):
            raise InvalidWatchlistSymbolError(
                "display_symbol must use the format SYMBOL.NSE or SYMBOL.BSE"
            )

        return normalized

    async def list_items(self, user_id: int) -> list[WatchlistItem]:
        return await self._repository.list_for_user(user_id)

    async def add_item(
        self,
        user_id: int,
        display_symbol: str,
    ) -> WatchlistItem:
        normalized_symbol = self.normalize_display_symbol(display_symbol)

        existing = await self._repository.get_by_symbol(
            user_id,
            normalized_symbol,
        )
        if existing is not None:
            raise WatchlistItemAlreadyExistsError(
                f"{normalized_symbol} is already in the watchlist."
            )

        exchange = normalized_symbol.rsplit(".", maxsplit=1)[1]

        item = await self._repository.add(
            user_id=user_id,
            display_symbol=normalized_symbol,
            exchange=exchange,
        )
        await self._session.commit()

        return item

    async def remove_item(
        self,
        user_id: int,
        display_symbol: str,
    ) -> None:
        normalized_symbol = self.normalize_display_symbol(display_symbol)

        await self._repository.delete(
            user_id,
            normalized_symbol,
        )
        await self._session.commit()
