"""Application ports for the financial_health module."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from app.modules.financial_health.domain.entities import (
    FinancialHealthSnapshot,
)
from app.modules.financial_statements.domain.entities import (
    FinancialStatementPeriod,
    FinancialStatements,
)


class FinancialStatementsProviderPort(Protocol):
    """Abstraction for retrieving existing financial statements."""

    async def get_financial_statements(
        self,
        display_symbol: str,
        *,
        period: FinancialStatementPeriod,
    ) -> FinancialStatements:
        """Return financial statements for the requested symbol."""
        ...


class FinancialHealthCalculatorPort(Protocol):
    """Abstraction for deterministic financial-health scoring."""

    def calculate_snapshot(
        self,
        financial_statements: FinancialStatements,
        *,
        calculated_at: datetime,
    ) -> FinancialHealthSnapshot:
        """Calculate a financial-health snapshot from statement data."""
        ...
