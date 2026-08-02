"""Application ports for Multibagger Potential analysis."""

from __future__ import annotations

from typing import Protocol

from app.modules.company_fundamentals.domain.entities import (
    CompanyFundamentals,
)
from app.modules.financial_health.domain.entities import (
    FinancialHealthSnapshot,
)
from app.modules.multibagger.domain.entities import (
    MultibaggerPotentialSnapshot,
)
from app.modules.stock_analysis.domain.entities import (
    StockAnalysisSnapshot,
)


class FundamentalsProviderPort(Protocol):
    async def get_fundamentals(
        self,
        display_symbol: str,
    ) -> CompanyFundamentals:
        """Return current company fundamentals."""


class FinancialHealthProviderPort(Protocol):
    async def get_financial_health(
        self,
        display_symbol: str,
        *,
        period: str,
    ) -> FinancialHealthSnapshot:
        """Return deterministic financial-health analysis."""


class StockAnalysisProviderPort(Protocol):
    async def get_stock_analysis(
        self,
        display_symbol: str,
        *,
        interval: str,
        technical_period: str,
        financial_period: str,
    ) -> StockAnalysisSnapshot:
        """Return combined technical and financial stock analysis."""


class MultibaggerCalculatorPort(Protocol):
    def calculate_snapshot(
        self,
        fundamentals: CompanyFundamentals,
        financial_health: FinancialHealthSnapshot | None,
        stock_analysis: StockAnalysisSnapshot | None,
    ) -> MultibaggerPotentialSnapshot:
        """Calculate one deterministic potential snapshot."""
