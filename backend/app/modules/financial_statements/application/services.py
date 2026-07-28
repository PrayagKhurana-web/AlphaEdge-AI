"""Application service for the financial_statements module."""

from __future__ import annotations

from app.modules.financial_statements.application.ports import (
    FinancialStatementsProviderPort,
)
from app.modules.financial_statements.domain.entities import (
    FinancialStatementPeriod,
    FinancialStatements,
)
from app.modules.financial_statements.domain.exceptions import (
    InvalidFinancialStatementsRequestError,
)


class FinancialStatementsService:
    """Coordinates financial-statements retrieval."""

    def __init__(
        self,
        provider: FinancialStatementsProviderPort,
    ) -> None:
        self._provider = provider

    async def get_financial_statements(
        self,
        display_symbol: str,
        *,
        period: str,
    ) -> FinancialStatements:
        normalized_symbol = display_symbol.strip()

        if not normalized_symbol:
            raise InvalidFinancialStatementsRequestError(
                "Display symbol is required."
            )

        try:
            normalized_period = FinancialStatementPeriod(period.strip().lower())
        except ValueError as exc:
            raise InvalidFinancialStatementsRequestError(
                "Period must be either 'annual' or 'quarterly'."
            ) from exc

        return await self._provider.get_financial_statements(
            normalized_symbol,
            normalized_period,
        )
