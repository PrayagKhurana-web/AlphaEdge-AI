"""Application service for combined stock analysis."""

from __future__ import annotations

from app.modules.stock_analysis.application.ports import (
    FinancialHealthProviderPort,
    StockAnalysisCalculatorPort,
    TechnicalAnalysisProviderPort,
)
from app.modules.stock_analysis.domain.entities import (
    StockAnalysisSnapshot,
)


class StockAnalysisService:
    """Orchestrate technical and financial analysis."""

    def __init__(
        self,
        technical_provider: TechnicalAnalysisProviderPort,
        financial_provider: FinancialHealthProviderPort,
        calculator: StockAnalysisCalculatorPort,
    ) -> None:
        self._technical_provider = technical_provider
        self._financial_provider = financial_provider
        self._calculator = calculator

    async def get_stock_analysis(
        self,
        display_symbol: str,
        *,
        interval: str = "1d",
        technical_period: str = "1y",
        financial_period: str = "annual",
    ) -> StockAnalysisSnapshot:
        normalized_symbol = display_symbol.strip()

        if not normalized_symbol:
            raise ValueError("Display symbol is required.")

        technical = (
            await self._technical_provider.get_technical_analysis(
                normalized_symbol,
                interval=interval,
                period=technical_period,
            )
        )

        financial = None

        try:
            financial = (
                await self._financial_provider.get_financial_health(
                    normalized_symbol,
                    period=financial_period,
                )
            )
        except Exception:
            # A valid technical outlook is still useful when upstream
            # financial statements are temporarily unavailable.
            financial = None

        return self._calculator.calculate_snapshot(
            technical,
            financial,
        )
