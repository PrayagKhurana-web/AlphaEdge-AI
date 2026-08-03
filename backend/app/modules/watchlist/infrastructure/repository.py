from __future__ import annotations

from datetime import timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.watchlist.application.ports import WatchlistRepository
from app.modules.watchlist.domain.entities import WatchlistItem
from app.modules.watchlist.domain.exceptions import (
    WatchlistItemAlreadyExistsError,
    WatchlistItemNotFoundError,
)
from app.modules.watchlist.infrastructure.models import WatchlistItemModel


class SqlAlchemyWatchlistRepository(WatchlistRepository):
    """MySQL-backed implementation of the watchlist repository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_entity(model: WatchlistItemModel) -> WatchlistItem:
        return WatchlistItem(
            id=model.id,
            user_id=model.user_id,
            display_symbol=model.display_symbol,
            exchange=model.exchange,
            created_at=(
                model.created_at
                if model.created_at.tzinfo is not None
                else model.created_at.replace(tzinfo=timezone.utc)
            ),
        )

    async def list_for_user(self, user_id: int) -> list[WatchlistItem]:
        statement = (
            select(WatchlistItemModel)
            .where(WatchlistItemModel.user_id == user_id)
            .order_by(
                WatchlistItemModel.created_at.desc(),
                WatchlistItemModel.id.desc(),
            )
        )
        result = await self._session.execute(statement)

        return [
            self._to_entity(model)
            for model in result.scalars().all()
        ]

    async def get_by_symbol(
        self,
        user_id: int,
        display_symbol: str,
    ) -> WatchlistItem | None:
        statement = select(WatchlistItemModel).where(
            WatchlistItemModel.user_id == user_id,
            WatchlistItemModel.display_symbol == display_symbol,
        )
        result = await self._session.execute(statement)
        model = result.scalar_one_or_none()

        return self._to_entity(model) if model is not None else None

    async def add(
        self,
        user_id: int,
        display_symbol: str,
        exchange: str,
    ) -> WatchlistItem:
        model = WatchlistItemModel(
            user_id=user_id,
            display_symbol=display_symbol,
            exchange=exchange,
        )
        self._session.add(model)

        try:
            await self._session.flush()
            await self._session.refresh(model)
        except IntegrityError as error:
            await self._session.rollback()
            raise WatchlistItemAlreadyExistsError(
                f"{display_symbol} is already in the watchlist."
            ) from error

        return self._to_entity(model)

    async def delete(
        self,
        user_id: int,
        display_symbol: str,
    ) -> None:
        statement = select(WatchlistItemModel).where(
            WatchlistItemModel.user_id == user_id,
            WatchlistItemModel.display_symbol == display_symbol,
        )
        result = await self._session.execute(statement)
        model = result.scalar_one_or_none()

        if model is None:
            raise WatchlistItemNotFoundError(
                f"{display_symbol} is not in the watchlist."
            )

        await self._session.delete(model)
        await self._session.flush()
