"""Deterministic calculator for the financial_health module."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, DivisionByZero, InvalidOperation

from app.modules.financial_health.application.ports import (
    FinancialHealthCalculatorPort,
)
from app.modules.financial_health.domain.entities import (
    FinancialHealthObservation,
    FinancialHealthObservationType,
    FinancialHealthRating,
    FinancialHealthSnapshot,
)
from app.modules.financial_health.domain.exceptions import (
    FinancialHealthCalculationError,
    InsufficientFinancialHealthDataError,
)
from app.modules.financial_statements.domain.entities import (
    FinancialStatementRecord,
    FinancialStatements,
)


class FinancialHealthCalculator(FinancialHealthCalculatorPort):
    """Calculate rule-based company financial-health scores."""

    def calculate_snapshot(
        self,
        financial_statements: FinancialStatements,
        *,
        calculated_at: datetime,
    ) -> FinancialHealthSnapshot:
        if calculated_at.tzinfo is None:
            raise FinancialHealthCalculationError(
                "calculated_at must be timezone-aware."
            )

        if len(financial_statements.statements) < 2:
            raise InsufficientFinancialHealthDataError(
                "At least two reporting periods are required."
            )

        latest = financial_statements.statements[0]
        previous = financial_statements.statements[1]

        revenue_growth = self._growth(
            latest.total_revenue,
            previous.total_revenue,
        )
        net_income_growth = self._growth(
            latest.net_income,
            previous.net_income,
        )
        operating_cash_flow_growth = self._growth(
            latest.operating_cash_flow,
            previous.operating_cash_flow,
        )
        free_cash_flow_growth = self._growth(
            latest.free_cash_flow,
            previous.free_cash_flow,
        )

        ebitda_margin = self._ratio(
            latest.ebitda,
            latest.total_revenue,
        )
        net_profit_margin = self._ratio(
            latest.net_income,
            latest.total_revenue,
        )
        debt_to_equity = self._ratio(
            latest.total_debt,
            latest.shareholder_equity,
        )
        cash_conversion_ratio = self._ratio(
            latest.operating_cash_flow,
            latest.net_income,
        )

        growth_score = self._average_scores(
            self._growth_score(revenue_growth),
            self._growth_score(net_income_growth),
        )

        profitability_score = self._average_scores(
            self._margin_score(ebitda_margin),
            self._margin_score(net_profit_margin),
        )

        balance_sheet_score = self._debt_score(debt_to_equity)

        cash_flow_score = self._average_scores(
            self._growth_score(operating_cash_flow_growth),
            self._growth_score(free_cash_flow_growth),
            self._cash_conversion_score(cash_conversion_ratio),
        )

        overall_score = round(
            growth_score * 0.30
            + profitability_score * 0.25
            + balance_sheet_score * 0.20
            + cash_flow_score * 0.25
        )

        observations = self._build_observations(
            revenue_growth=revenue_growth,
            net_income_growth=net_income_growth,
            ebitda_margin=ebitda_margin,
            net_profit_margin=net_profit_margin,
            debt_to_equity=debt_to_equity,
            operating_cash_flow_growth=operating_cash_flow_growth,
            free_cash_flow_growth=free_cash_flow_growth,
            cash_conversion_ratio=cash_conversion_ratio,
        )

        return FinancialHealthSnapshot(
            symbol=financial_statements.symbol,
            display_symbol=financial_statements.display_symbol,
            company_name=financial_statements.company_name,
            exchange=financial_statements.exchange,
            period=financial_statements.period,
            currency=financial_statements.currency,
            overall_score=overall_score,
            rating=self._rating(overall_score),
            growth_score=growth_score,
            profitability_score=profitability_score,
            balance_sheet_score=balance_sheet_score,
            cash_flow_score=cash_flow_score,
            revenue_growth=revenue_growth,
            net_income_growth=net_income_growth,
            ebitda_margin=ebitda_margin,
            net_profit_margin=net_profit_margin,
            debt_to_equity=debt_to_equity,
            operating_cash_flow_growth=operating_cash_flow_growth,
            free_cash_flow_growth=free_cash_flow_growth,
            cash_conversion_ratio=cash_conversion_ratio,
            observations=observations,
            calculated_at=calculated_at,
        )

    @staticmethod
    def _growth(
        current: Decimal | None,
        previous: Decimal | None,
    ) -> Decimal | None:
        if current is None or previous is None or previous == 0:
            return None

        try:
            return (current - previous) / abs(previous)
        except (DivisionByZero, InvalidOperation):
            return None

    @staticmethod
    def _ratio(
        numerator: Decimal | None,
        denominator: Decimal | None,
    ) -> Decimal | None:
        if numerator is None or denominator is None or denominator == 0:
            return None

        try:
            return numerator / denominator
        except (DivisionByZero, InvalidOperation):
            return None

    @staticmethod
    def _growth_score(value: Decimal | None) -> int:
        if value is None:
            return 50
        if value >= Decimal("0.20"):
            return 100
        if value >= Decimal("0.10"):
            return 85
        if value >= Decimal("0.05"):
            return 70
        if value >= Decimal("0"):
            return 55
        if value >= Decimal("-0.10"):
            return 35
        return 15

    @staticmethod
    def _margin_score(value: Decimal | None) -> int:
        if value is None:
            return 50
        if value >= Decimal("0.25"):
            return 100
        if value >= Decimal("0.15"):
            return 85
        if value >= Decimal("0.10"):
            return 70
        if value >= Decimal("0.05"):
            return 55
        if value >= Decimal("0"):
            return 35
        return 10

    @staticmethod
    def _debt_score(value: Decimal | None) -> int:
        if value is None:
            return 50
        if value <= Decimal("0.25"):
            return 100
        if value <= Decimal("0.50"):
            return 85
        if value <= Decimal("1"):
            return 70
        if value <= Decimal("1.50"):
            return 50
        if value <= Decimal("2"):
            return 30
        return 10

    @staticmethod
    def _cash_conversion_score(value: Decimal | None) -> int:
        if value is None:
            return 50
        if value >= Decimal("1.20"):
            return 100
        if value >= Decimal("1"):
            return 85
        if value >= Decimal("0.75"):
            return 70
        if value >= Decimal("0.50"):
            return 50
        if value >= Decimal("0"):
            return 30
        return 10

    @staticmethod
    def _average_scores(*scores: int) -> int:
        return round(sum(scores) / len(scores))

    @staticmethod
    def _rating(score: int) -> FinancialHealthRating:
        if score >= 85:
            return FinancialHealthRating.STRONG
        if score >= 70:
            return FinancialHealthRating.HEALTHY
        if score >= 50:
            return FinancialHealthRating.MIXED
        if score >= 30:
            return FinancialHealthRating.WEAK
        return FinancialHealthRating.HIGH_RISK

    def _build_observations(
        self,
        *,
        revenue_growth: Decimal | None,
        net_income_growth: Decimal | None,
        ebitda_margin: Decimal | None,
        net_profit_margin: Decimal | None,
        debt_to_equity: Decimal | None,
        operating_cash_flow_growth: Decimal | None,
        free_cash_flow_growth: Decimal | None,
        cash_conversion_ratio: Decimal | None,
    ) -> tuple[FinancialHealthObservation, ...]:
        observations: list[FinancialHealthObservation] = []

        observations.append(
            self._growth_observation(
                "growth",
                "Revenue",
                revenue_growth,
            )
        )
        observations.append(
            self._growth_observation(
                "growth",
                "Net income",
                net_income_growth,
            )
        )
        observations.append(
            self._margin_observation(
                "profitability",
                "EBITDA margin",
                ebitda_margin,
            )
        )
        observations.append(
            self._margin_observation(
                "profitability",
                "Net profit margin",
                net_profit_margin,
            )
        )
        observations.append(
            self._debt_observation(debt_to_equity)
        )
        observations.append(
            self._growth_observation(
                "cash_flow",
                "Operating cash flow",
                operating_cash_flow_growth,
            )
        )
        observations.append(
            self._growth_observation(
                "cash_flow",
                "Free cash flow",
                free_cash_flow_growth,
            )
        )
        observations.append(
            self._cash_conversion_observation(
                cash_conversion_ratio
            )
        )

        return tuple(observations)

    @staticmethod
    def _growth_observation(
        category: str,
        label: str,
        value: Decimal | None,
    ) -> FinancialHealthObservation:
        if value is None:
            return FinancialHealthObservation(
                category=category,
                observation_type=FinancialHealthObservationType.NEUTRAL,
                message=f"{label} growth could not be calculated.",
            )

        if value >= Decimal("0.10"):
            tone = FinancialHealthObservationType.POSITIVE
            message = f"{label} is growing strongly."
        elif value >= Decimal("0"):
            tone = FinancialHealthObservationType.NEUTRAL
            message = f"{label} is growing modestly."
        else:
            tone = FinancialHealthObservationType.NEGATIVE
            message = f"{label} has declined from the previous period."

        return FinancialHealthObservation(
            category=category,
            observation_type=tone,
            message=message,
        )

    @staticmethod
    def _margin_observation(
        category: str,
        label: str,
        value: Decimal | None,
    ) -> FinancialHealthObservation:
        if value is None:
            return FinancialHealthObservation(
                category=category,
                observation_type=FinancialHealthObservationType.NEUTRAL,
                message=f"{label} is not available.",
            )

        if value >= Decimal("0.15"):
            tone = FinancialHealthObservationType.POSITIVE
            message = f"{label} is strong."
        elif value >= Decimal("0.05"):
            tone = FinancialHealthObservationType.NEUTRAL
            message = f"{label} is moderate."
        else:
            tone = FinancialHealthObservationType.NEGATIVE
            message = f"{label} is weak."

        return FinancialHealthObservation(
            category=category,
            observation_type=tone,
            message=message,
        )

    @staticmethod
    def _debt_observation(
        value: Decimal | None,
    ) -> FinancialHealthObservation:
        if value is None:
            tone = FinancialHealthObservationType.NEUTRAL
            message = "Debt-to-equity could not be calculated."
        elif value <= Decimal("0.50"):
            tone = FinancialHealthObservationType.POSITIVE
            message = "Debt is low relative to shareholder equity."
        elif value <= Decimal("1"):
            tone = FinancialHealthObservationType.NEUTRAL
            message = "Debt is moderate relative to shareholder equity."
        else:
            tone = FinancialHealthObservationType.NEGATIVE
            message = "Debt is high relative to shareholder equity."

        return FinancialHealthObservation(
            category="balance_sheet",
            observation_type=tone,
            message=message,
        )

    @staticmethod
    def _cash_conversion_observation(
        value: Decimal | None,
    ) -> FinancialHealthObservation:
        if value is None:
            tone = FinancialHealthObservationType.NEUTRAL
            message = "Profit-to-cash conversion could not be calculated."
        elif value >= Decimal("1"):
            tone = FinancialHealthObservationType.POSITIVE
            message = "Reported profit is converting strongly into operating cash."
        elif value >= Decimal("0.50"):
            tone = FinancialHealthObservationType.NEUTRAL
            message = "Profit-to-cash conversion is moderate."
        else:
            tone = FinancialHealthObservationType.NEGATIVE
            message = "Reported profit is converting weakly into operating cash."

        return FinancialHealthObservation(
            category="cash_flow",
            observation_type=tone,
            message=message,
        )
