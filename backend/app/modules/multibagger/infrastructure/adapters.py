"""Adapters reusing existing AlphaEdge services."""

from __future__ import annotations

from app.modules.company_fundamentals.application.services import (
    CompanyFundamentalsService,
)
from app.modules.company_fundamentals.domain.entities import (
    CompanyFundamentals,
)
from app.modules.financial_health.application.services import (
    FinancialHealthService,
)
from app.modules.financial_health.domain.entities import (
    FinancialHealthSnapshot,
)
from app.modules.stock_analysis.application.services import (
    StockAnalysisService,
)
from app.modules.stock_analysis.domain.entities import (
    StockAnalysisSnapshot,
)


class CompanyFundamentalsMultibaggerAdapter:
    """Expose fundamentals through the Multibagger port."""

    def __init__(
        self,
        service: CompanyFundamentalsService,
    ) -> None:
        self._service = service

    async def get_fundamentals(
        self,
        display_symbol: str,
    ) -> CompanyFundamentals:
        return await self._service.get_fundamentals(
            display_symbol
        )


class FinancialHealthMultibaggerAdapter:
    """Expose financial health through the Multibagger port."""

    def __init__(
        self,
        service: FinancialHealthService,
    ) -> None:
        self._service = service

    async def get_financial_health(
        self,
        display_symbol: str,
        *,
        period: str,
    ) -> FinancialHealthSnapshot:
        return await self._service.get_financial_health(
            display_symbol,
            period=period,
        )


class StockAnalysisMultibaggerAdapter:
    """Expose stock analysis through the Multibagger port."""

    def __init__(
        self,
        service: StockAnalysisService,
    ) -> None:
        self._service = service

    async def get_stock_analysis(
        self,
        display_symbol: str,
        *,
        interval: str,
        technical_period: str,
        financial_period: str,
    ) -> StockAnalysisSnapshot:
        return await self._service.get_stock_analysis(
            display_symbol,
            interval=interval,
            technical_period=technical_period,
            financial_period=financial_period,
        )
