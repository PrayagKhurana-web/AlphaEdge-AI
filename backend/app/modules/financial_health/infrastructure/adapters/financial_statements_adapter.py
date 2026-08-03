"""Adapter connecting financial_health to financial_statements."""

from __future__ import annotations

from app.modules.financial_health.application.ports import (
    FinancialStatementsProviderPort,
)
from app.modules.financial_statements.application.services import (
    FinancialStatementsService,
)
from app.modules.financial_statements.domain.entities import (
    FinancialStatementPeriod,
    FinancialStatements,
)


class FinancialStatementsServiceAdapter(
    FinancialStatementsProviderPort
):
    """Delegate statement retrieval to the existing service."""

    def __init__(
        self,
        financial_statements_service: FinancialStatementsService,
    ) -> None:
        self._financial_statements_service = (
            financial_statements_service
        )

    async def get_financial_statements(
        self,
        display_symbol: str,
        *,
        period: FinancialStatementPeriod,
    ) -> FinancialStatements:
        return await (
            self._financial_statements_service
            .get_financial_statements(
                display_symbol,
                period=period.value,
            )
        )
