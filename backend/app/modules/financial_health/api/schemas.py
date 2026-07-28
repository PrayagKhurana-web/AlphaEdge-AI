"""API schemas for the financial_health module."""

from __future__ import annotations

from decimal import Decimal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_serializer

from app.modules.financial_health.domain.entities import (
    FinancialHealthObservation,
    FinancialHealthSnapshot,
)


class FinancialHealthObservationResponse(BaseModel):
    """One rule-based financial-health observation."""

    model_config = ConfigDict(
        populate_by_name=True,
        serialize_by_alias=True,
    )

    category: str
    observation_type: str = Field(alias="observationType")
    message: str

    @classmethod
    def from_domain(
        cls,
        observation: FinancialHealthObservation,
    ) -> "FinancialHealthObservationResponse":
        return cls(
            category=observation.category,
            observationType=observation.observation_type.value,
            message=observation.message,
        )


class FinancialHealthResponse(BaseModel):
    """Financial-health assessment returned by the API."""

    model_config = ConfigDict(
        populate_by_name=True,
        serialize_by_alias=True,
    )

    symbol: str
    display_symbol: str = Field(alias="displaySymbol")
    company_name: str = Field(alias="companyName")
    exchange: str
    period: str
    currency: str | None

    overall_score: int = Field(alias="overallScore")
    rating: str

    growth_score: int = Field(alias="growthScore")
    profitability_score: int = Field(alias="profitabilityScore")
    balance_sheet_score: int = Field(alias="balanceSheetScore")
    cash_flow_score: int = Field(alias="cashFlowScore")

    revenue_growth: Decimal | None = Field(alias="revenueGrowth")
    net_income_growth: Decimal | None = Field(alias="netIncomeGrowth")
    ebitda_margin: Decimal | None = Field(alias="ebitdaMargin")
    net_profit_margin: Decimal | None = Field(alias="netProfitMargin")
    debt_to_equity: Decimal | None = Field(alias="debtToEquity")
    operating_cash_flow_growth: Decimal | None = Field(
        alias="operatingCashFlowGrowth"
    )
    free_cash_flow_growth: Decimal | None = Field(
        alias="freeCashFlowGrowth"
    )
    cash_conversion_ratio: Decimal | None = Field(
        alias="cashConversionRatio"
    )

    observations: list[FinancialHealthObservationResponse]
    calculated_at: AwareDatetime = Field(alias="calculatedAt")

    @field_serializer(
        "revenue_growth",
        "net_income_growth",
        "ebitda_margin",
        "net_profit_margin",
        "debt_to_equity",
        "operating_cash_flow_growth",
        "free_cash_flow_growth",
        "cash_conversion_ratio",
        when_used="json",
    )
    def serialize_decimal_fields(
        self,
        value: Decimal | None,
    ) -> str | None:
        if value is None:
            return None

        return str(value)

    @classmethod
    def from_domain(
        cls,
        snapshot: FinancialHealthSnapshot,
    ) -> "FinancialHealthResponse":
        return cls(
            symbol=snapshot.symbol,
            displaySymbol=snapshot.display_symbol,
            companyName=snapshot.company_name,
            exchange=snapshot.exchange.value,
            period=snapshot.period.value,
            currency=snapshot.currency,
            overallScore=snapshot.overall_score,
            rating=snapshot.rating.value,
            growthScore=snapshot.growth_score,
            profitabilityScore=snapshot.profitability_score,
            balanceSheetScore=snapshot.balance_sheet_score,
            cashFlowScore=snapshot.cash_flow_score,
            revenueGrowth=snapshot.revenue_growth,
            netIncomeGrowth=snapshot.net_income_growth,
            ebitdaMargin=snapshot.ebitda_margin,
            netProfitMargin=snapshot.net_profit_margin,
            debtToEquity=snapshot.debt_to_equity,
            operatingCashFlowGrowth=(
                snapshot.operating_cash_flow_growth
            ),
            freeCashFlowGrowth=snapshot.free_cash_flow_growth,
            cashConversionRatio=snapshot.cash_conversion_ratio,
            observations=[
                FinancialHealthObservationResponse.from_domain(
                    observation
                )
                for observation in snapshot.observations
            ],
            calculatedAt=snapshot.calculated_at,
        )
