"""Application orchestration for Multibagger Potential."""

from __future__ import annotations

import asyncio

from app.modules.multibagger.application.ports import (
    FinancialHealthProviderPort,
    FundamentalsProviderPort,
    MultibaggerCalculatorPort,
    StockAnalysisProviderPort,
)
from app.modules.multibagger.domain.entities import (
    MultibaggerPotentialSnapshot,
)
from app.modules.multibagger.domain.exceptions import (
    InvalidMultibaggerRequestError,
)


class MultibaggerPotentialService:
    """Coordinate reusable AlphaEdge analysis services."""

    def __init__(
        self,
        *,
        fundamentals_provider: FundamentalsProviderPort,
        financial_health_provider: FinancialHealthProviderPort,
        stock_analysis_provider: StockAnalysisProviderPort,
        calculator: MultibaggerCalculatorPort,
    ) -> None:
        self._fundamentals_provider = fundamentals_provider
        self._financial_health_provider = (
            financial_health_provider
        )
        self._stock_analysis_provider = stock_analysis_provider
        self._calculator = calculator

    async def analyse_stock(
        self,
        display_symbol: str,
        *,
        interval: str = "1d",
        technical_period: str = "1y",
        financial_period: str = "annual",
    ) -> MultibaggerPotentialSnapshot:
        normalized_symbol = display_symbol.strip().upper()

        if not normalized_symbol:
            raise InvalidMultibaggerRequestError(
                "Display symbol is required."
            )

        fundamentals_task = asyncio.create_task(
            self._fundamentals_provider.get_fundamentals(
                normalized_symbol
            )
        )

        financial_task = asyncio.create_task(
            self._financial_health_provider.get_financial_health(
                normalized_symbol,
                period=financial_period,
            )
        )

        analysis_task = asyncio.create_task(
            self._stock_analysis_provider.get_stock_analysis(
                normalized_symbol,
                interval=interval,
                technical_period=technical_period,
                financial_period=financial_period,
            )
        )

        fundamentals_result, financial_result, analysis_result = (
            await asyncio.gather(
                fundamentals_task,
                financial_task,
                analysis_task,
                return_exceptions=True,
            )
        )

        if isinstance(fundamentals_result, BaseException):
            raise fundamentals_result

        financial_health = (
            None
            if isinstance(financial_result, BaseException)
            else financial_result
        )

        stock_analysis = (
            None
            if isinstance(analysis_result, BaseException)
            else analysis_result
        )

        return self._calculator.calculate_snapshot(
            fundamentals_result,
            financial_health,
            stock_analysis,
        )
