from __future__ import annotations

from datetime import timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.portfolio.application.ports import PortfolioRepository
from app.modules.portfolio.domain.entities import PortfolioHolding
from app.modules.portfolio.domain.exceptions import (
    PortfolioHoldingAlreadyExistsError,
    PortfolioHoldingNotFoundError,
)
from app.modules.portfolio.infrastructure.models import (
    PortfolioHoldingModel,
)


class SqlAlchemyPortfolioRepository(PortfolioRepository):
    """MySQL-backed portfolio repository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _ensure_utc(value):
        if value.tzinfo is not None:
            return value

        return value.replace(tzinfo=timezone.utc)

    @classmethod
    def _to_entity(
        cls,
        model: PortfolioHoldingModel,
    ) -> PortfolioHolding:
        return PortfolioHolding(
            id=model.id,
            user_id=model.user_id,
            display_symbol=model.display_symbol,
            exchange=model.exchange,
            quantity=Decimal(model.quantity),
            average_buy_price=Decimal(model.average_buy_price),
            created_at=cls._ensure_utc(model.created_at),
            updated_at=cls._ensure_utc(model.updated_at),
        )

    async def list_for_user(
        self,
        user_id: int,
    ) -> list[PortfolioHolding]:
        statement = (
            select(PortfolioHoldingModel)
            .where(PortfolioHoldingModel.user_id == user_id)
            .order_by(
                PortfolioHoldingModel.created_at.desc(),
                PortfolioHoldingModel.id.desc(),
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
    ) -> PortfolioHolding | None:
        statement = select(PortfolioHoldingModel).where(
            PortfolioHoldingModel.user_id == user_id,
            PortfolioHoldingModel.display_symbol == display_symbol,
        )

        result = await self._session.execute(statement)
        model = result.scalar_one_or_none()

        return self._to_entity(model) if model is not None else None

    async def add(
        self,
        user_id: int,
        display_symbol: str,
        exchange: str,
        quantity: Decimal,
        average_buy_price: Decimal,
    ) -> PortfolioHolding:
        model = PortfolioHoldingModel(
            user_id=user_id,
            display_symbol=display_symbol,
            exchange=exchange,
            quantity=quantity,
            average_buy_price=average_buy_price,
        )

        self._session.add(model)

        try:
            await self._session.flush()
            await self._session.refresh(model)
        except IntegrityError as error:
            await self._session.rollback()

            raise PortfolioHoldingAlreadyExistsError(
                f"{display_symbol} already exists in the portfolio."
            ) from error

        return self._to_entity(model)

    async def update(
        self,
        user_id: int,
        display_symbol: str,
        quantity: Decimal,
        average_buy_price: Decimal,
    ) -> PortfolioHolding:
        statement = select(PortfolioHoldingModel).where(
            PortfolioHoldingModel.user_id == user_id,
            PortfolioHoldingModel.display_symbol == display_symbol,
        )

        result = await self._session.execute(statement)
        model = result.scalar_one_or_none()

        if model is None:
            raise PortfolioHoldingNotFoundError(
                f"{display_symbol} is not in the portfolio."
            )

        model.quantity = quantity
        model.average_buy_price = average_buy_price

        await self._session.flush()
        await self._session.refresh(model)

        return self._to_entity(model)

    async def delete(
        self,
        user_id: int,
        display_symbol: str,
    ) -> None:
        statement = select(PortfolioHoldingModel).where(
            PortfolioHoldingModel.user_id == user_id,
            PortfolioHoldingModel.display_symbol == display_symbol,
        )

        result = await self._session.execute(statement)
        model = result.scalar_one_or_none()

        if model is None:
            raise PortfolioHoldingNotFoundError(
                f"{display_symbol} is not in the portfolio."
            )

        await self._session.delete(model)
        await self._session.flush()
