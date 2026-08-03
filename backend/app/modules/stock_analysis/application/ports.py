"""Application ports for stock_analysis."""

from __future__ import annotations

from typing import Protocol

from app.modules.financial_health.domain.entities import (
    FinancialHealthSnapshot,
)
from app.modules.quant_engine.domain.entities import (
    TechnicalAnalysisSnapshot,
)
from app.modules.stock_analysis.domain.entities import (
    StockAnalysisSnapshot,
)


class TechnicalAnalysisProviderPort(Protocol):
    async def get_technical_analysis(
        self,
        display_symbol: str,
        *,
        interval: str,
        period: str,
        currency: str | None = None,
    ) -> TechnicalAnalysisSnapshot:
        ...


class FinancialHealthProviderPort(Protocol):
    async def get_financial_health(
        self,
        display_symbol: str,
        *,
        period: str,
    ) -> FinancialHealthSnapshot:
        ...


class StockAnalysisCalculatorPort(Protocol):
    def calculate_snapshot(
        self,
        technical: TechnicalAnalysisSnapshot,
        financial: FinancialHealthSnapshot | None,
    ) -> StockAnalysisSnapshot:
        ...
