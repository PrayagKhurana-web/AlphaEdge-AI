"""Application ports for the financial_statements module."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.modules.financial_statements.domain.entities import (
    FinancialStatementPeriod,
    FinancialStatements,
)


class FinancialStatementsProviderPort(ABC):
    """Provider contract for retrieving normalised financial statements."""

    @abstractmethod
    async def get_financial_statements(
        self,
        display_symbol: str,
        period: FinancialStatementPeriod,
    ) -> FinancialStatements:
        """Return financial statements for the requested symbol and period."""
        raise NotImplementedError
