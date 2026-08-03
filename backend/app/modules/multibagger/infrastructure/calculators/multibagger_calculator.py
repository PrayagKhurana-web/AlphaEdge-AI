"""Deterministic Multibagger Potential calculator."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from app.modules.company_fundamentals.domain.entities import (
    CompanyFundamentals,
)
from app.modules.financial_health.domain.entities import (
    FinancialHealthRating,
    FinancialHealthSnapshot,
)
from app.modules.multibagger.domain.entities import (
    MultibaggerObservation,
    MultibaggerObservationType,
    MultibaggerPotentialCategory,
    MultibaggerPotentialSnapshot,
)
from app.modules.stock_analysis.domain.entities import (
    StockAnalysisSnapshot,
    StockOutlook,
    StockRiskLevel,
)


class MultibaggerPotentialCalculator:
    """Calculate a transparent long-term potential score."""

    GROWTH_WEIGHT = Decimal("0.30")
    FINANCIAL_WEIGHT = Decimal("0.25")
    VALUATION_WEIGHT = Decimal("0.15")
    MOMENTUM_WEIGHT = Decimal("0.20")
    RISK_WEIGHT = Decimal("0.10")

    @staticmethod
    def _clamp(value: int | Decimal) -> int:
        normalized = int(
            Decimal(value).quantize(
                Decimal("1"),
                rounding=ROUND_HALF_UP,
            )
        )
        return max(0, min(100, normalized))

    @staticmethod
    def _ratio_score(
        value: Decimal | None,
        *,
        excellent: Decimal,
        good: Decimal,
        neutral: Decimal,
        weak: Decimal,
    ) -> int:
        if value is None:
            return 50

        if value >= excellent:
            return 100
        if value >= good:
            return 80
        if value >= neutral:
            return 60
        if value >= weak:
            return 35
        return 10

    @staticmethod
    def _inverse_score(
        value: Decimal | None,
        *,
        excellent: Decimal,
        good: Decimal,
        neutral: Decimal,
        weak: Decimal,
    ) -> int:
        if value is None:
            return 50

        if value <= excellent:
            return 100
        if value <= good:
            return 80
        if value <= neutral:
            return 60
        if value <= weak:
            return 35
        return 10

    def calculate_snapshot(
        self,
        fundamentals: CompanyFundamentals,
        financial_health: FinancialHealthSnapshot | None,
        stock_analysis: StockAnalysisSnapshot | None,
    ) -> MultibaggerPotentialSnapshot:
        observations: list[MultibaggerObservation] = []

        growth_score = self._growth_score(
            fundamentals,
            financial_health,
            observations,
        )

        financial_score = self._financial_score(
            fundamentals,
            financial_health,
            observations,
        )

        valuation_score = self._valuation_score(
            fundamentals,
            observations,
        )

        momentum_score = self._momentum_score(
            stock_analysis,
            observations,
        )

        risk_score = self._risk_score(
            fundamentals,
            financial_health,
            stock_analysis,
            observations,
        )

        weighted_score = (
            Decimal(growth_score) * self.GROWTH_WEIGHT
            + Decimal(financial_score) * self.FINANCIAL_WEIGHT
            + Decimal(valuation_score) * self.VALUATION_WEIGHT
            + Decimal(momentum_score) * self.MOMENTUM_WEIGHT
            + Decimal(risk_score) * self.RISK_WEIGHT
        )

        completeness = self._data_completeness(
            fundamentals,
            financial_health,
            stock_analysis,
        )

        # Missing information should reduce confidence without
        # automatically describing the company as fundamentally weak.
        completeness_multiplier = (
            Decimal("0.85")
            + Decimal(completeness)
            / Decimal("100")
            * Decimal("0.15")
        )

        potential_score = self._clamp(
            weighted_score * completeness_multiplier
        )

        return MultibaggerPotentialSnapshot(
            symbol=fundamentals.symbol,
            display_symbol=fundamentals.display_symbol,
            company_name=fundamentals.company_name,
            potential_score=potential_score,
            potential_category=self._category(
                potential_score
            ),
            growth_quality_score=growth_score,
            financial_strength_score=financial_score,
            valuation_attractiveness_score=valuation_score,
            momentum_score=momentum_score,
            risk_quality_score=risk_score,
            data_completeness_score=completeness,
            market_cap=fundamentals.market_cap,
            revenue_growth=fundamentals.revenue_growth,
            earnings_growth=fundamentals.earnings_growth,
            return_on_equity=fundamentals.return_on_equity,
            debt_to_equity=fundamentals.debt_to_equity,
            trailing_pe=fundamentals.trailing_pe,
            price_to_book=fundamentals.price_to_book,
            observations=tuple(observations),
            calculated_at=datetime.now(timezone.utc),
        )

    def _growth_score(
        self,
        fundamentals: CompanyFundamentals,
        financial: FinancialHealthSnapshot | None,
        observations: list[MultibaggerObservation],
    ) -> int:
        revenue_score = self._ratio_score(
            fundamentals.revenue_growth,
            excellent=Decimal("0.25"),
            good=Decimal("0.15"),
            neutral=Decimal("0.08"),
            weak=Decimal("0"),
        )

        earnings_score = self._ratio_score(
            fundamentals.earnings_growth,
            excellent=Decimal("0.30"),
            good=Decimal("0.18"),
            neutral=Decimal("0.08"),
            weak=Decimal("0"),
        )

        financial_growth = (
            financial.growth_score
            if financial is not None
            else 50
        )

        score = self._clamp(
            Decimal(revenue_score) * Decimal("0.35")
            + Decimal(earnings_score) * Decimal("0.35")
            + Decimal(financial_growth) * Decimal("0.30")
        )

        if score >= 75:
            observations.append(
                MultibaggerObservation(
                    category="growth",
                    observation_type=(
                        MultibaggerObservationType.POSITIVE
                    ),
                    message=(
                        "Revenue and earnings indicators show "
                        "strong growth quality."
                    ),
                )
            )
        elif score < 45:
            observations.append(
                MultibaggerObservation(
                    category="growth",
                    observation_type=(
                        MultibaggerObservationType.NEGATIVE
                    ),
                    message=(
                        "Growth indicators are weak, negative, "
                        "or insufficiently consistent."
                    ),
                )
            )
        else:
            observations.append(
                MultibaggerObservation(
                    category="growth",
                    observation_type=(
                        MultibaggerObservationType.NEUTRAL
                    ),
                    message=(
                        "Growth indicators are presently moderate."
                    ),
                )
            )

        return score

    def _financial_score(
        self,
        fundamentals: CompanyFundamentals,
        financial: FinancialHealthSnapshot | None,
        observations: list[MultibaggerObservation],
    ) -> int:
        roe_score = self._ratio_score(
            fundamentals.return_on_equity,
            excellent=Decimal("0.22"),
            good=Decimal("0.16"),
            neutral=Decimal("0.10"),
            weak=Decimal("0"),
        )

        debt_score = self._inverse_score(
            fundamentals.debt_to_equity,
            excellent=Decimal("0.30"),
            good=Decimal("0.70"),
            neutral=Decimal("1.20"),
            weak=Decimal("2.00"),
        )

        cash_score = 50

        if fundamentals.operating_cash_flow is not None:
            cash_score = (
                85
                if fundamentals.operating_cash_flow > 0
                else 15
            )

        health_score = (
            financial.overall_score
            if financial is not None
            else 50
        )

        score = self._clamp(
            Decimal(roe_score) * Decimal("0.25")
            + Decimal(debt_score) * Decimal("0.25")
            + Decimal(cash_score) * Decimal("0.20")
            + Decimal(health_score) * Decimal("0.30")
        )

        if score >= 75:
            tone = MultibaggerObservationType.POSITIVE
            message = (
                "Profitability, leverage, and cash-flow indicators "
                "suggest strong financial quality."
            )
        elif score < 45:
            tone = MultibaggerObservationType.NEGATIVE
            message = (
                "Financial strength is constrained by profitability, "
                "debt, cash flow, or financial-health concerns."
            )
        else:
            tone = MultibaggerObservationType.NEUTRAL
            message = (
                "Financial strength is mixed and requires monitoring."
            )

        observations.append(
            MultibaggerObservation(
                category="financial_strength",
                observation_type=tone,
                message=message,
            )
        )

        return score

    def _valuation_score(
        self,
        fundamentals: CompanyFundamentals,
        observations: list[MultibaggerObservation],
    ) -> int:
        pe_score = self._inverse_score(
            fundamentals.trailing_pe,
            excellent=Decimal("15"),
            good=Decimal("25"),
            neutral=Decimal("40"),
            weak=Decimal("65"),
        )

        forward_pe_score = self._inverse_score(
            fundamentals.forward_pe,
            excellent=Decimal("14"),
            good=Decimal("24"),
            neutral=Decimal("38"),
            weak=Decimal("60"),
        )

        price_to_book_score = self._inverse_score(
            fundamentals.price_to_book,
            excellent=Decimal("2"),
            good=Decimal("4"),
            neutral=Decimal("7"),
            weak=Decimal("12"),
        )

        ev_ebitda_score = self._inverse_score(
            fundamentals.enterprise_to_ebitda,
            excellent=Decimal("10"),
            good=Decimal("16"),
            neutral=Decimal("24"),
            weak=Decimal("35"),
        )

        score = self._clamp(
            (
                Decimal(pe_score)
                + Decimal(forward_pe_score)
                + Decimal(price_to_book_score)
                + Decimal(ev_ebitda_score)
            )
            / Decimal("4")
        )

        if score >= 75:
            tone = MultibaggerObservationType.POSITIVE
            message = (
                "Available valuation multiples appear attractive "
                "relative to the scoring thresholds."
            )
        elif score < 40:
            tone = MultibaggerObservationType.NEGATIVE
            message = (
                "Available valuation multiples indicate a demanding "
                "price and limited margin of safety."
            )
        else:
            tone = MultibaggerObservationType.NEUTRAL
            message = (
                "Valuation appears neither clearly cheap nor "
                "extremely expensive."
            )

        observations.append(
            MultibaggerObservation(
                category="valuation",
                observation_type=tone,
                message=message,
            )
        )

        return score

    def _momentum_score(
        self,
        analysis: StockAnalysisSnapshot | None,
        observations: list[MultibaggerObservation],
    ) -> int:
        if analysis is None:
            observations.append(
                MultibaggerObservation(
                    category="momentum",
                    observation_type=(
                        MultibaggerObservationType.NEUTRAL
                    ),
                    message=(
                        "Technical momentum data is currently "
                        "unavailable."
                    ),
                )
            )
            return 50

        outlook_bonus = {
            StockOutlook.BULLISH: 15,
            StockOutlook.NEUTRAL: 0,
            StockOutlook.BEARISH: -20,
        }[analysis.outlook]

        score = self._clamp(
            Decimal(analysis.technical_score)
            * Decimal("0.70")
            + Decimal(analysis.confidence_score)
            * Decimal("0.30")
            + Decimal(outlook_bonus)
        )

        if analysis.outlook is StockOutlook.BULLISH:
            tone = MultibaggerObservationType.POSITIVE
            message = (
                "Current technical momentum supports the "
                "long-term screening score."
            )
        elif analysis.outlook is StockOutlook.BEARISH:
            tone = MultibaggerObservationType.NEGATIVE
            message = (
                "Current technical momentum is bearish despite "
                "the long-term screening factors."
            )
        else:
            tone = MultibaggerObservationType.NEUTRAL
            message = (
                "Current technical momentum is neutral."
            )

        observations.append(
            MultibaggerObservation(
                category="momentum",
                observation_type=tone,
                message=message,
            )
        )

        return score

    def _risk_score(
        self,
        fundamentals: CompanyFundamentals,
        financial: FinancialHealthSnapshot | None,
        analysis: StockAnalysisSnapshot | None,
        observations: list[MultibaggerObservation],
    ) -> int:
        score = 70
        warnings: list[str] = []

        if (
            fundamentals.debt_to_equity is not None
            and fundamentals.debt_to_equity > Decimal("2")
        ):
            score -= 25
            warnings.append("high debt-to-equity")

        if (
            fundamentals.operating_cash_flow is not None
            and fundamentals.operating_cash_flow <= 0
        ):
            score -= 20
            warnings.append("non-positive operating cash flow")

        if (
            fundamentals.earnings_growth is not None
            and fundamentals.earnings_growth < 0
        ):
            score -= 15
            warnings.append("negative earnings growth")

        if financial is not None and financial.rating in {
            FinancialHealthRating.WEAK,
            FinancialHealthRating.HIGH_RISK,
        }:
            score -= 20
            warnings.append("weak financial-health rating")

        if (
            analysis is not None
            and analysis.risk_level is StockRiskLevel.HIGH
        ):
            score -= 15
            warnings.append("high market risk")

        normalized_score = self._clamp(score)

        if warnings:
            observations.append(
                MultibaggerObservation(
                    category="risk",
                    observation_type=(
                        MultibaggerObservationType.NEGATIVE
                    ),
                    message=(
                        "Risk flags detected: "
                        + ", ".join(warnings)
                        + "."
                    ),
                )
            )
        else:
            observations.append(
                MultibaggerObservation(
                    category="risk",
                    observation_type=(
                        MultibaggerObservationType.POSITIVE
                    ),
                    message=(
                        "No major red flags were detected from "
                        "the available inputs."
                    ),
                )
            )

        return normalized_score

    @staticmethod
    def _data_completeness(
        fundamentals: CompanyFundamentals,
        financial: FinancialHealthSnapshot | None,
        analysis: StockAnalysisSnapshot | None,
    ) -> int:
        values = (
            fundamentals.market_cap,
            fundamentals.revenue_growth,
            fundamentals.earnings_growth,
            fundamentals.return_on_equity,
            fundamentals.debt_to_equity,
            fundamentals.operating_cash_flow,
            fundamentals.free_cash_flow,
            fundamentals.trailing_pe,
            fundamentals.forward_pe,
            fundamentals.price_to_book,
            fundamentals.enterprise_to_ebitda,
        )

        available = sum(
            value is not None
            for value in values
        )

        if financial is not None:
            available += 1

        if analysis is not None:
            available += 1

        total = len(values) + 2

        return round(available / total * 100)

    @staticmethod
    def _category(
        score: int,
    ) -> MultibaggerPotentialCategory:
        if score >= 80:
            return MultibaggerPotentialCategory.VERY_HIGH
        if score >= 65:
            return MultibaggerPotentialCategory.HIGH
        if score >= 50:
            return MultibaggerPotentialCategory.MODERATE
        if score >= 35:
            return MultibaggerPotentialCategory.LOW
        return MultibaggerPotentialCategory.VERY_LOW
