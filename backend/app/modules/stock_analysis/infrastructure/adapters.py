"""Adapters reusing existing AlphaEdge services."""

from __future__ import annotations

from app.modules.financial_health.application.services import (
    FinancialHealthService,
)
from app.modules.financial_health.domain.entities import (
    FinancialHealthSnapshot,
)
from app.modules.quant_engine.application.services import (
    QuantEngineService,
)
from app.modules.quant_engine.domain.entities import (
    TechnicalAnalysisSnapshot,
)


class QuantEngineAnalysisAdapter:
    """Expose QuantEngineService through the analysis port."""

    def __init__(self, service: QuantEngineService) -> None:
        self._service = service

    async def get_technical_analysis(
        self,
        display_symbol: str,
        *,
        interval: str,
        period: str,
        currency: str | None = None,
    ) -> TechnicalAnalysisSnapshot:
        return await self._service.get_technical_analysis(
            display_symbol,
            interval=interval,
            period=period,
            currency=currency,
        )


class FinancialHealthAnalysisAdapter:
    """Expose FinancialHealthService through the analysis port."""

    def __init__(self, service: FinancialHealthService) -> None:
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
