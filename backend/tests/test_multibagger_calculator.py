from datetime import datetime, timezone
from decimal import Decimal

from app.modules.company_fundamentals.domain.entities import (
    CompanyFundamentals,
)
from app.modules.financial_health.domain.entities import (
    FinancialHealthRating,
    FinancialHealthSnapshot,
)
from app.modules.financial_statements.domain.entities import (
    FinancialStatementPeriod,
)
from app.modules.multibagger.domain.entities import (
    MultibaggerObservationType,
    MultibaggerPotentialCategory,
)
from app.modules.multibagger.infrastructure.calculators.multibagger_calculator import (
    MultibaggerPotentialCalculator,
)
from app.modules.stock_analysis.domain.entities import (
    AnalysisReason,
    AnalysisReasonType,
    StockAnalysisSnapshot,
    StockOutlook,
    StockRiskLevel,
)
from app.modules.stock_search.domain.entities import StockExchange


NOW = datetime(2026, 8, 3, tzinfo=timezone.utc)


def make_fundamentals(
    **changes,
) -> CompanyFundamentals:
    values = {
        "symbol": "TEST",
        "display_symbol": "TEST.NSE",
        "company_name": "Test Limited",
        "exchange": StockExchange.NSE,
        "sector": "Technology",
        "industry": "Software",
        "website": None,
        "business_summary": None,
        "market_cap": Decimal("50000000000"),
        "enterprise_value": Decimal("48000000000"),
        "trailing_pe": Decimal("22"),
        "forward_pe": Decimal("18"),
        "price_to_book": Decimal("3"),
        "enterprise_to_revenue": Decimal("4"),
        "enterprise_to_ebitda": Decimal("14"),
        "trailing_eps": Decimal("12"),
        "forward_eps": Decimal("15"),
        "book_value_per_share": Decimal("80"),
        "return_on_equity": Decimal("0.20"),
        "return_on_assets": Decimal("0.12"),
        "profit_margin": Decimal("0.18"),
        "operating_margin": Decimal("0.24"),
        "revenue_growth": Decimal("0.20"),
        "earnings_growth": Decimal("0.25"),
        "total_revenue": Decimal("10000000000"),
        "net_income": Decimal("1800000000"),
        "total_cash": Decimal("3000000000"),
        "total_debt": Decimal("1000000000"),
        "debt_to_equity": Decimal("0.35"),
        "free_cash_flow": Decimal("1500000000"),
        "operating_cash_flow": Decimal("2100000000"),
        "dividend_rate": None,
        "dividend_yield": None,
        "payout_ratio": None,
        "fifty_two_week_high": Decimal("500"),
        "fifty_two_week_low": Decimal("250"),
        "fifty_day_average": Decimal("430"),
        "two_hundred_day_average": Decimal("390"),
        "currency": "INR",
        "fetched_at": NOW,
    }
    values.update(changes)
    return CompanyFundamentals(**values)


def make_financial_health(
    *,
    score: int = 82,
    rating: FinancialHealthRating = (
        FinancialHealthRating.STRONG
    ),
) -> FinancialHealthSnapshot:
    return FinancialHealthSnapshot(
        symbol="TEST",
        display_symbol="TEST.NSE",
        company_name="Test Limited",
        exchange=StockExchange.NSE,
        period=FinancialStatementPeriod.ANNUAL,
        currency="INR",
        overall_score=score,
        rating=rating,
        growth_score=85,
        profitability_score=82,
        balance_sheet_score=88,
        cash_flow_score=80,
        revenue_growth=Decimal("0.20"),
        net_income_growth=Decimal("0.25"),
        ebitda_margin=Decimal("0.24"),
        net_profit_margin=Decimal("0.18"),
        debt_to_equity=Decimal("0.35"),
        operating_cash_flow_growth=Decimal("0.18"),
        free_cash_flow_growth=Decimal("0.16"),
        cash_conversion_ratio=Decimal("1.10"),
        observations=(),
        calculated_at=NOW,
    )


def make_analysis(
    *,
    outlook: StockOutlook = StockOutlook.BULLISH,
    risk: StockRiskLevel = StockRiskLevel.LOW,
) -> StockAnalysisSnapshot:
    return StockAnalysisSnapshot(
        symbol="TEST",
        display_symbol="TEST.NSE",
        outlook=outlook,
        bullish_probability=72,
        bearish_probability=28,
        confidence_score=74,
        risk_level=risk,
        time_horizon="medium_term",
        overall_score=78,
        technical_score=80,
        financial_score=82,
        market_activity_score=65,
        current_price=Decimal("450"),
        nearest_support=Decimal("420"),
        nearest_resistance=Decimal("480"),
        reasons=(
            AnalysisReason(
                category="trend",
                reason_type=AnalysisReasonType.POSITIVE,
                message="Trend is constructive.",
            ),
        ),
        calculated_at=NOW,
    )


def test_strong_company_receives_high_potential_score() -> None:
    result = MultibaggerPotentialCalculator().calculate_snapshot(
        make_fundamentals(),
        make_financial_health(),
        make_analysis(),
    )

    assert result.potential_score >= 65
    assert result.potential_category in {
        MultibaggerPotentialCategory.HIGH,
        MultibaggerPotentialCategory.VERY_HIGH,
    }
    assert result.data_completeness_score == 100


def test_high_debt_and_negative_cash_flow_create_warning() -> None:
    result = MultibaggerPotentialCalculator().calculate_snapshot(
        make_fundamentals(
            debt_to_equity=Decimal("3.5"),
            operating_cash_flow=Decimal("-100"),
            earnings_growth=Decimal("-0.20"),
        ),
        make_financial_health(
            score=30,
            rating=FinancialHealthRating.HIGH_RISK,
        ),
        make_analysis(
            outlook=StockOutlook.BEARISH,
            risk=StockRiskLevel.HIGH,
        ),
    )

    risk_observation = next(
        observation
        for observation in result.observations
        if observation.category == "risk"
    )

    assert (
        risk_observation.observation_type
        is MultibaggerObservationType.NEGATIVE
    )
    assert result.risk_quality_score < 50


def test_missing_optional_sources_still_produces_snapshot() -> None:
    result = MultibaggerPotentialCalculator().calculate_snapshot(
        make_fundamentals(),
        None,
        None,
    )

    assert 0 <= result.potential_score <= 100
    assert result.data_completeness_score < 100
    assert result.momentum_score == 50


def test_score_components_remain_between_zero_and_one_hundred() -> None:
    result = MultibaggerPotentialCalculator().calculate_snapshot(
        make_fundamentals(),
        make_financial_health(),
        make_analysis(),
    )

    components = (
        result.growth_quality_score,
        result.financial_strength_score,
        result.valuation_attractiveness_score,
        result.momentum_score,
        result.risk_quality_score,
    )

    assert all(0 <= value <= 100 for value in components)


def test_expensive_valuation_reduces_valuation_score() -> None:
    result = MultibaggerPotentialCalculator().calculate_snapshot(
        make_fundamentals(
            trailing_pe=Decimal("100"),
            forward_pe=Decimal("90"),
            price_to_book=Decimal("20"),
            enterprise_to_ebitda=Decimal("50"),
        ),
        make_financial_health(),
        make_analysis(),
    )

    assert result.valuation_attractiveness_score < 40


def test_methodology_does_not_claim_guaranteed_returns() -> None:
    result = MultibaggerPotentialCalculator().calculate_snapshot(
        make_fundamentals(),
        make_financial_health(),
        make_analysis(),
    )

    messages = " ".join(
        observation.message.lower()
        for observation in result.observations
    )

    assert "guarantee" not in messages
    assert result.methodology_version == "multibagger-rules-v1"
