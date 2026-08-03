from __future__ import annotations

from decimal import Decimal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
)

from app.modules.portfolio.domain.entities import (
    PortfolioHolding,
    PortfolioPosition,
    PortfolioValuation,
)


class PortfolioHoldingPayload(BaseModel):
    """Payload used to create or update a holding."""

    model_config = ConfigDict(
        populate_by_name=True,
        serialize_by_alias=True,
    )

    display_symbol: str | None = Field(
        default=None,
        alias="displaySymbol",
        min_length=5,
        max_length=32,
        examples=["RELIANCE.NSE"],
    )
    quantity: Decimal = Field(gt=0, examples=["5"])
    average_buy_price: Decimal = Field(
        alias="averageBuyPrice",
        gt=0,
        examples=["1250.50"],
    )


class AddPortfolioHoldingRequest(PortfolioHoldingPayload):
    """Payload for creating a portfolio holding."""

    display_symbol: str = Field(
        alias="displaySymbol",
        min_length=5,
        max_length=32,
        examples=["RELIANCE.NSE"],
    )


class UpdatePortfolioHoldingRequest(BaseModel):
    """Payload for updating a portfolio holding."""

    model_config = ConfigDict(
        populate_by_name=True,
        serialize_by_alias=True,
    )

    quantity: Decimal = Field(gt=0, examples=["7"])
    average_buy_price: Decimal = Field(
        alias="averageBuyPrice",
        gt=0,
        examples=["1275.25"],
    )


class PortfolioHoldingResponse(BaseModel):
    """Persisted holding returned by create/update endpoints."""

    model_config = ConfigDict(
        populate_by_name=True,
        serialize_by_alias=True,
    )

    id: int
    display_symbol: str = Field(alias="displaySymbol")
    exchange: str
    quantity: Decimal
    average_buy_price: Decimal = Field(alias="averageBuyPrice")
    created_at: AwareDatetime = Field(alias="createdAt")
    updated_at: AwareDatetime = Field(alias="updatedAt")

    @field_serializer(
        "quantity",
        "average_buy_price",
        when_used="json",
    )
    def serialize_decimal(self, value: Decimal) -> str:
        return format(value, "f")

    @classmethod
    def from_domain(
        cls,
        holding: PortfolioHolding,
    ) -> "PortfolioHoldingResponse":
        return cls(
            id=holding.id,
            displaySymbol=holding.display_symbol,
            exchange=holding.exchange,
            quantity=holding.quantity,
            averageBuyPrice=holding.average_buy_price,
            createdAt=holding.created_at,
            updatedAt=holding.updated_at,
        )


class PortfolioPositionResponse(BaseModel):
    """One holding enriched with current valuation."""

    model_config = ConfigDict(
        populate_by_name=True,
        serialize_by_alias=True,
    )

    id: int
    display_symbol: str = Field(alias="displaySymbol")
    company_name: str = Field(alias="companyName")
    exchange: str
    quantity: Decimal
    average_buy_price: Decimal = Field(alias="averageBuyPrice")
    current_price: Decimal = Field(alias="currentPrice")
    invested_amount: Decimal = Field(alias="investedAmount")
    current_value: Decimal = Field(alias="currentValue")
    profit_loss: Decimal = Field(alias="profitLoss")
    return_percent: Decimal = Field(alias="returnPercent")
    allocation_percent: Decimal = Field(alias="allocationPercent")

    @field_serializer(
        "quantity",
        "average_buy_price",
        "current_price",
        "invested_amount",
        "current_value",
        "profit_loss",
        "return_percent",
        "allocation_percent",
        when_used="json",
    )
    def serialize_decimal(self, value: Decimal) -> str:
        return format(value, "f")

    @classmethod
    def from_domain(
        cls,
        position: PortfolioPosition,
    ) -> "PortfolioPositionResponse":
        holding = position.holding

        return cls(
            id=holding.id,
            displaySymbol=holding.display_symbol,
            companyName=position.company_name,
            exchange=holding.exchange,
            quantity=holding.quantity,
            averageBuyPrice=holding.average_buy_price,
            currentPrice=position.current_price,
            investedAmount=position.invested_amount,
            currentValue=position.current_value,
            profitLoss=position.profit_loss,
            returnPercent=position.return_percent,
            allocationPercent=position.allocation_percent,
        )


class PortfolioResponse(BaseModel):
    """Complete current portfolio valuation."""

    model_config = ConfigDict(
        populate_by_name=True,
        serialize_by_alias=True,
    )

    positions: list[PortfolioPositionResponse]
    count: int
    total_invested: Decimal = Field(alias="totalInvested")
    total_current_value: Decimal = Field(alias="totalCurrentValue")
    total_profit_loss: Decimal = Field(alias="totalProfitLoss")
    total_return_percent: Decimal = Field(alias="totalReturnPercent")

    @field_serializer(
        "total_invested",
        "total_current_value",
        "total_profit_loss",
        "total_return_percent",
        when_used="json",
    )
    def serialize_decimal(self, value: Decimal) -> str:
        return format(value, "f")

    @classmethod
    def from_domain(
        cls,
        valuation: PortfolioValuation,
    ) -> "PortfolioResponse":
        return cls(
            positions=[
                PortfolioPositionResponse.from_domain(position)
                for position in valuation.positions
            ],
            count=len(valuation.positions),
            totalInvested=valuation.total_invested,
            totalCurrentValue=valuation.total_current_value,
            totalProfitLoss=valuation.total_profit_loss,
            totalReturnPercent=valuation.total_return_percent,
        )
