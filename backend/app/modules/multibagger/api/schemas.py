"""API schemas for Multibagger Potential."""

from __future__ import annotations

from decimal import Decimal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
)

from app.modules.multibagger.domain.entities import (
    MultibaggerObservation,
    MultibaggerPotentialSnapshot,
)
from app.modules.multibagger.domain.rankings import (
    MultibaggerRankingsSnapshot,
)


class MultibaggerObservationResponse(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        serialize_by_alias=True,
    )

    category: str
    observation_type: str = Field(
        alias="observationType"
    )
    message: str

    @classmethod
    def from_domain(
        cls,
        observation: MultibaggerObservation,
    ) -> "MultibaggerObservationResponse":
        return cls(
            category=observation.category,
            observationType=(
                observation.observation_type.value
            ),
            message=observation.message,
        )


class MultibaggerPotentialResponse(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        serialize_by_alias=True,
    )

    symbol: str
    display_symbol: str = Field(alias="displaySymbol")
    company_name: str = Field(alias="companyName")

    potential_score: int = Field(alias="potentialScore")
    potential_category: str = Field(
        alias="potentialCategory"
    )

    growth_quality_score: int = Field(
        alias="growthQualityScore"
    )
    financial_strength_score: int = Field(
        alias="financialStrengthScore"
    )
    valuation_attractiveness_score: int = Field(
        alias="valuationAttractivenessScore"
    )
    momentum_score: int = Field(alias="momentumScore")
    risk_quality_score: int = Field(
        alias="riskQualityScore"
    )
    data_completeness_score: int = Field(
        alias="dataCompletenessScore"
    )

    market_cap: Decimal | None = Field(alias="marketCap")
    revenue_growth: Decimal | None = Field(
        alias="revenueGrowth"
    )
    earnings_growth: Decimal | None = Field(
        alias="earningsGrowth"
    )
    return_on_equity: Decimal | None = Field(
        alias="returnOnEquity"
    )
    debt_to_equity: Decimal | None = Field(
        alias="debtToEquity"
    )
    trailing_pe: Decimal | None = Field(
        alias="trailingPe"
    )
    price_to_book: Decimal | None = Field(
        alias="priceToBook"
    )

    observations: list[MultibaggerObservationResponse]
    calculated_at: AwareDatetime = Field(
        alias="calculatedAt"
    )
    methodology_version: str = Field(
        alias="methodologyVersion"
    )

    disclaimer: str = (
        "This is a deterministic screening score, not a "
        "guarantee of multibagger returns or investment advice."
    )

    @field_serializer(
        "market_cap",
        "revenue_growth",
        "earnings_growth",
        "return_on_equity",
        "debt_to_equity",
        "trailing_pe",
        "price_to_book",
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
        snapshot: MultibaggerPotentialSnapshot,
    ) -> "MultibaggerPotentialResponse":
        return cls(
            symbol=snapshot.symbol,
            displaySymbol=snapshot.display_symbol,
            companyName=snapshot.company_name,
            potentialScore=snapshot.potential_score,
            potentialCategory=(
                snapshot.potential_category.value
            ),
            growthQualityScore=(
                snapshot.growth_quality_score
            ),
            financialStrengthScore=(
                snapshot.financial_strength_score
            ),
            valuationAttractivenessScore=(
                snapshot.valuation_attractiveness_score
            ),
            momentumScore=snapshot.momentum_score,
            riskQualityScore=snapshot.risk_quality_score,
            dataCompletenessScore=(
                snapshot.data_completeness_score
            ),
            marketCap=snapshot.market_cap,
            revenueGrowth=snapshot.revenue_growth,
            earningsGrowth=snapshot.earnings_growth,
            returnOnEquity=snapshot.return_on_equity,
            debtToEquity=snapshot.debt_to_equity,
            trailingPe=snapshot.trailing_pe,
            priceToBook=snapshot.price_to_book,
            observations=[
                MultibaggerObservationResponse.from_domain(
                    observation
                )
                for observation in snapshot.observations
            ],
            calculatedAt=snapshot.calculated_at,
            methodologyVersion=(
                snapshot.methodology_version
            ),
        )


class MultibaggerWeightsResponse(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        serialize_by_alias=True,
    )

    growth: int
    financial_strength: int = Field(
        alias="financialStrength"
    )
    valuation: int
    momentum: int
    risk: int


class MultibaggerRankingsResponse(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        serialize_by_alias=True,
    )

    rankings: list[MultibaggerPotentialResponse]
    failed_symbols: list[str] = Field(alias="failedSymbols")

    universe_size: int = Field(alias="universeSize")
    successful_count: int = Field(alias="successfulCount")
    failed_count: int = Field(alias="failedCount")
    returned_count: int = Field(alias="returnedCount")
    minimum_score: int = Field(alias="minimumScore")
    result_limit: int = Field(alias="resultLimit")

    weights: MultibaggerWeightsResponse

    generated_at: AwareDatetime = Field(alias="generatedAt")
    cache_expires_at: AwareDatetime = Field(
        alias="cacheExpiresAt"
    )

    @classmethod
    def from_domain(
        cls,
        snapshot: MultibaggerRankingsSnapshot,
    ) -> "MultibaggerRankingsResponse":
        return cls(
            rankings=[
                MultibaggerPotentialResponse.from_domain(
                    ranking
                )
                for ranking in snapshot.rankings
            ],
            failedSymbols=list(snapshot.failed_symbols),
            universeSize=snapshot.universe_size,
            successfulCount=snapshot.successful_count,
            failedCount=len(snapshot.failed_symbols),
            returnedCount=len(snapshot.rankings),
            minimumScore=snapshot.minimum_score,
            resultLimit=snapshot.result_limit,
            weights=MultibaggerWeightsResponse(
                growth=snapshot.growth_weight,
                financialStrength=(
                    snapshot.financial_strength_weight
                ),
                valuation=snapshot.valuation_weight,
                momentum=snapshot.momentum_weight,
                risk=snapshot.risk_weight,
            ),
            generatedAt=snapshot.generated_at,
            cacheExpiresAt=snapshot.cache_expires_at,
        )
