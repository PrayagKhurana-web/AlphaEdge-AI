"""Application service for the financial_health module."""

from __future__ import annotations

from datetime import datetime, timezone

from app.modules.financial_health.application.ports import (
    FinancialHealthCalculatorPort,
    FinancialStatementsProviderPort,
)
from app.modules.financial_health.domain.entities import (
    FinancialHealthSnapshot,
)
from app.modules.financial_health.domain.exceptions import (
    InvalidFinancialHealthRequestError,
)
from app.modules.financial_statements.domain.entities import (
    FinancialStatementPeriod,
)


class FinancialHealthService:
    """Orchestrate deterministic financial-health analysis."""

    def __init__(
        self,
        financial_statements_provider: FinancialStatementsProviderPort,
        financial_health_calculator: FinancialHealthCalculatorPort,
    ) -> None:
        self._financial_statements_provider = financial_statements_provider
        self._financial_health_calculator = financial_health_calculator

    async def get_financial_health(
        self,
        display_symbol: str,
        *,
        period: str = "annual",
    ) -> FinancialHealthSnapshot:
        normalized_symbol = display_symbol.strip()

        if not normalized_symbol:
            raise InvalidFinancialHealthRequestError(
                "Display symbol is required."
            )

        try:
            normalized_period = FinancialStatementPeriod(
                period.strip().lower()
            )
        except ValueError as exc:
            raise InvalidFinancialHealthRequestError(
                "Period must be either 'annual' or 'quarterly'."
            ) from exc

        financial_statements = (
            await self._financial_statements_provider.get_financial_statements(
                normalized_symbol,
                period=normalized_period,
            )
        )

        return self._financial_health_calculator.calculate_snapshot(
            financial_statements,
            calculated_at=datetime.now(timezone.utc),
        )
