"""API schemas for stock_analysis."""

from __future__ import annotations

from decimal import Decimal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
)

from app.modules.stock_analysis.domain.entities import (
    AnalysisReason,
    StockAnalysisSnapshot,
)


class AnalysisReasonResponse(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        serialize_by_alias=True,
    )

    category: str
    reason_type: str = Field(alias="reasonType")
    message: str

    @classmethod
    def from_domain(
        cls,
        reason: AnalysisReason,
    ) -> "AnalysisReasonResponse":
        return cls(
            category=reason.category,
            reasonType=reason.reason_type.value,
            message=reason.message,
        )


class StockAnalysisResponse(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        serialize_by_alias=True,
    )

    symbol: str
    display_symbol: str = Field(alias="displaySymbol")
    outlook: str

    bullish_probability: int = Field(alias="bullishProbability")
    bearish_probability: int = Field(alias="bearishProbability")
    confidence_score: int = Field(alias="confidenceScore")
    risk_level: str = Field(alias="riskLevel")
    time_horizon: str = Field(alias="timeHorizon")

    overall_score: int = Field(alias="overallScore")
    technical_score: int = Field(alias="technicalScore")
    financial_score: int = Field(alias="financialScore")
    market_activity_score: int = Field(alias="marketActivityScore")

    current_price: Decimal = Field(alias="currentPrice")
    nearest_support: Decimal | None = Field(alias="nearestSupport")
    nearest_resistance: Decimal | None = Field(
        alias="nearestResistance"
    )

    reasons: list[AnalysisReasonResponse]
    calculated_at: AwareDatetime = Field(alias="calculatedAt")

    @field_serializer(
        "current_price",
        "nearest_support",
        "nearest_resistance",
        when_used="json",
    )
    def serialize_decimal(
        self,
        value: Decimal | None,
    ) -> str | None:
        return None if value is None else str(value)

    @classmethod
    def from_domain(
        cls,
        snapshot: StockAnalysisSnapshot,
    ) -> "StockAnalysisResponse":
        return cls(
            symbol=snapshot.symbol,
            displaySymbol=snapshot.display_symbol,
            outlook=snapshot.outlook.value,
            bullishProbability=snapshot.bullish_probability,
            bearishProbability=snapshot.bearish_probability,
            confidenceScore=snapshot.confidence_score,
            riskLevel=snapshot.risk_level.value,
            timeHorizon=snapshot.time_horizon,
            overallScore=snapshot.overall_score,
            technicalScore=snapshot.technical_score,
            financialScore=snapshot.financial_score,
            marketActivityScore=snapshot.market_activity_score,
            currentPrice=snapshot.current_price,
            nearestSupport=snapshot.nearest_support,
            nearestResistance=snapshot.nearest_resistance,
            reasons=[
                AnalysisReasonResponse.from_domain(reason)
                for reason in snapshot.reasons
            ],
            calculatedAt=snapshot.calculated_at,
        )
