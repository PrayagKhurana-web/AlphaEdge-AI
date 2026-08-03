from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.modules.multibagger.application.services import (
    MultibaggerPotentialService,
)
from app.modules.multibagger.domain.exceptions import (
    InvalidMultibaggerRequestError,
)


class FundamentalsProvider:
    async def get_fundamentals(self, display_symbol: str):
        return SimpleNamespace(
            display_symbol=display_symbol
        )


class FinancialProvider:
    async def get_financial_health(
        self,
        display_symbol: str,
        *,
        period: str,
    ):
        return SimpleNamespace(
            display_symbol=display_symbol,
            period=period,
        )


class FailingFinancialProvider:
    async def get_financial_health(
        self,
        display_symbol: str,
        *,
        period: str,
    ):
        raise RuntimeError("financial unavailable")


class AnalysisProvider:
    async def get_stock_analysis(
        self,
        display_symbol: str,
        *,
        interval: str,
        technical_period: str,
        financial_period: str,
    ):
        return SimpleNamespace(
            display_symbol=display_symbol,
            interval=interval,
        )


class Calculator:
    def calculate_snapshot(
        self,
        fundamentals,
        financial_health,
        stock_analysis,
    ):
        return {
            "fundamentals": fundamentals,
            "financial": financial_health,
            "analysis": stock_analysis,
        }


def make_service(
    financial_provider=None,
) -> MultibaggerPotentialService:
    return MultibaggerPotentialService(
        fundamentals_provider=FundamentalsProvider(),
        financial_health_provider=(
            financial_provider or FinancialProvider()
        ),
        stock_analysis_provider=AnalysisProvider(),
        calculator=Calculator(),
    )


@pytest.mark.asyncio
async def test_service_normalizes_symbol() -> None:
    result = await make_service().analyse_stock(
        "  test.nse  "
    )

    assert (
        result["fundamentals"].display_symbol
        == "TEST.NSE"
    )


@pytest.mark.asyncio
async def test_service_tolerates_optional_financial_failure() -> None:
    result = await make_service(
        FailingFinancialProvider()
    ).analyse_stock("TEST.NSE")

    assert result["financial"] is None
    assert result["analysis"] is not None


@pytest.mark.asyncio
async def test_service_rejects_empty_symbol() -> None:
    with pytest.raises(
        InvalidMultibaggerRequestError,
        match="Display symbol is required",
    ):
        await make_service().analyse_stock("   ")
