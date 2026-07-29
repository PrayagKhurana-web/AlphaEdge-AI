from __future__ import annotations

import re
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.portfolio.application.ports import PortfolioRepository
from app.modules.portfolio.domain.entities import (
    PortfolioHolding,
    PortfolioPosition,
    PortfolioValuation,
)
from app.modules.portfolio.domain.exceptions import (
    InvalidPortfolioHoldingError,
    PortfolioHoldingAlreadyExistsError,
)
from app.modules.stock_details.application.services import (
    StockQuoteService,
)


_DISPLAY_SYMBOL_PATTERN = re.compile(
    r"^[A-Z0-9][A-Z0-9&\-]{0,29}\.(NSE|BSE)$"
)

_MONEY_QUANTUM = Decimal("0.01")
_PERCENT_QUANTUM = Decimal("0.01")


class PortfolioService:
    """Coordinates persistence and live portfolio valuation."""

    def __init__(
        self,
        repository: PortfolioRepository,
        session: AsyncSession,
        quote_service: StockQuoteService,
    ) -> None:
        self._repository = repository
        self._session = session
        self._quote_service = quote_service

    @staticmethod
    def _normalize_display_symbol(display_symbol: str) -> str:
        normalized = display_symbol.strip().upper()

        if not _DISPLAY_SYMBOL_PATTERN.fullmatch(normalized):
            raise InvalidPortfolioHoldingError(
                "display_symbol must use the format SYMBOL.NSE or SYMBOL.BSE"
            )

        return normalized

    @staticmethod
    def _validate_positive_decimal(
        value: Decimal,
        field_name: str,
    ) -> Decimal:
        if not isinstance(value, Decimal):
            raise InvalidPortfolioHoldingError(
                f"{field_name} must be a decimal value."
            )

        if not value.is_finite() or value <= Decimal("0"):
            raise InvalidPortfolioHoldingError(
                f"{field_name} must be greater than zero."
            )

        return value

    @staticmethod
    def _money(value: Decimal) -> Decimal:
        return value.quantize(
            _MONEY_QUANTUM,
            rounding=ROUND_HALF_UP,
        )

    @staticmethod
    def _percent(value: Decimal) -> Decimal:
        return value.quantize(
            _PERCENT_QUANTUM,
            rounding=ROUND_HALF_UP,
        )

    async def list_holdings(
        self,
        user_id: int,
    ) -> list[PortfolioHolding]:
        return await self._repository.list_for_user(user_id)

    async def add_holding(
        self,
        user_id: int,
        display_symbol: str,
        quantity: Decimal,
        average_buy_price: Decimal,
    ) -> PortfolioHolding:
        normalized_symbol = self._normalize_display_symbol(display_symbol)
        quantity = self._validate_positive_decimal(
            quantity,
            "quantity",
        )
        average_buy_price = self._validate_positive_decimal(
            average_buy_price,
            "average_buy_price",
        )

        existing = await self._repository.get_by_symbol(
            user_id,
            normalized_symbol,
        )

        if existing is not None:
            raise PortfolioHoldingAlreadyExistsError(
                f"{normalized_symbol} already exists in the portfolio."
            )

        # This validates that the symbol exists and that quote retrieval works.
        await self._quote_service.get_quote(normalized_symbol)

        exchange = normalized_symbol.rsplit(".", maxsplit=1)[1]

        holding = await self._repository.add(
            user_id=user_id,
            display_symbol=normalized_symbol,
            exchange=exchange,
            quantity=quantity,
            average_buy_price=average_buy_price,
        )

        await self._session.commit()

        return holding

    async def update_holding(
        self,
        user_id: int,
        display_symbol: str,
        quantity: Decimal,
        average_buy_price: Decimal,
    ) -> PortfolioHolding:
        normalized_symbol = self._normalize_display_symbol(display_symbol)
        quantity = self._validate_positive_decimal(
            quantity,
            "quantity",
        )
        average_buy_price = self._validate_positive_decimal(
            average_buy_price,
            "average_buy_price",
        )

        holding = await self._repository.update(
            user_id=user_id,
            display_symbol=normalized_symbol,
            quantity=quantity,
            average_buy_price=average_buy_price,
        )

        await self._session.commit()

        return holding

    async def remove_holding(
        self,
        user_id: int,
        display_symbol: str,
    ) -> None:
        normalized_symbol = self._normalize_display_symbol(display_symbol)

        await self._repository.delete(
            user_id=user_id,
            display_symbol=normalized_symbol,
        )

        await self._session.commit()

    async def value_portfolio(
        self,
        user_id: int,
    ) -> PortfolioValuation:
        holdings = await self._repository.list_for_user(user_id)

        provisional_positions: list[
            tuple[
                PortfolioHolding,
                str,
                Decimal,
                Decimal,
                Decimal,
                Decimal,
                Decimal,
            ]
        ] = []

        total_invested = Decimal("0")
        total_current_value = Decimal("0")

        for holding in holdings:
            quote = await self._quote_service.get_quote(
                holding.display_symbol
            )

            invested_amount = (
                holding.quantity * holding.average_buy_price
            )
            current_value = holding.quantity * quote.price
            profit_loss = current_value - invested_amount

            return_percent = (
                profit_loss / invested_amount * Decimal("100")
                if invested_amount != Decimal("0")
                else Decimal("0")
            )

            provisional_positions.append(
                (
                    holding,
                    quote.company_name,
                    quote.price,
                    invested_amount,
                    current_value,
                    profit_loss,
                    return_percent,
                )
            )

            total_invested += invested_amount
            total_current_value += current_value

        positions: list[PortfolioPosition] = []

        for (
            holding,
            company_name,
            current_price,
            invested_amount,
            current_value,
            profit_loss,
            return_percent,
        ) in provisional_positions:
            allocation_percent = (
                current_value
                / total_current_value
                * Decimal("100")
                if total_current_value != Decimal("0")
                else Decimal("0")
            )

            positions.append(
                PortfolioPosition(
                    holding=holding,
                    company_name=company_name,
                    current_price=self._money(current_price),
                    invested_amount=self._money(invested_amount),
                    current_value=self._money(current_value),
                    profit_loss=self._money(profit_loss),
                    return_percent=self._percent(return_percent),
                    allocation_percent=self._percent(
                        allocation_percent
                    ),
                )
            )

        total_profit_loss = (
            total_current_value - total_invested
        )

        total_return_percent = (
            total_profit_loss
            / total_invested
            * Decimal("100")
            if total_invested != Decimal("0")
            else Decimal("0")
        )

        return PortfolioValuation(
            positions=positions,
            total_invested=self._money(total_invested),
            total_current_value=self._money(total_current_value),
            total_profit_loss=self._money(total_profit_loss),
            total_return_percent=self._percent(
                total_return_percent
            ),
        )
