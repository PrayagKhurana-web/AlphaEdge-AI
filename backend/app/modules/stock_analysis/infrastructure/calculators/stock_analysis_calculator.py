"""Explainable deterministic stock-analysis scoring."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from app.modules.financial_health.domain.entities import (
    FinancialHealthRating,
    FinancialHealthSnapshot,
)
from app.modules.quant_engine.domain.entities import (
    TechnicalAnalysisSnapshot,
    TechnicalSignal,
    TrendDirection,
)
from app.modules.stock_analysis.domain.entities import (
    AnalysisReason,
    AnalysisReasonType,
    StockAnalysisSnapshot,
    StockOutlook,
    StockRiskLevel,
)


class StockAnalysisCalculator:
    """Combine technical, financial and activity scores."""

    _TECHNICAL_WEIGHT = Decimal("0.60")
    _FINANCIAL_WEIGHT = Decimal("0.30")
    _ACTIVITY_WEIGHT = Decimal("0.10")

    def calculate_snapshot(
        self,
        technical: TechnicalAnalysisSnapshot,
        financial: FinancialHealthSnapshot | None,
    ) -> StockAnalysisSnapshot:
        technical_score, technical_reasons = (
            self._calculate_technical_score(technical)
        )

        financial_score, financial_reasons = (
            self._calculate_financial_score(financial)
        )

        activity_score, activity_reasons = (
            self._calculate_activity_score(technical)
        )

        overall_score = self._weighted_score(
            technical_score=technical_score,
            financial_score=financial_score,
            activity_score=activity_score,
        )

        bullish_probability = self._probability_from_score(
            overall_score
        )
        bearish_probability = 100 - bullish_probability

        outlook = self._outlook(overall_score)
        risk_level = self._risk_level(
            technical=technical,
            overall_score=overall_score,
            technical_score=technical_score,
            financial_score=financial_score,
            financial_available=financial is not None,
        )

        confidence_score = self._confidence_score(
            overall_score=overall_score,
            technical=technical,
            financial_available=financial is not None,
        )

        reasons = tuple(
            (
                technical_reasons
                + financial_reasons
                + activity_reasons
            )[:6]
        )

        return StockAnalysisSnapshot(
            symbol=technical.symbol,
            display_symbol=technical.display_symbol,
            outlook=outlook,
            bullish_probability=bullish_probability,
            bearish_probability=bearish_probability,
            confidence_score=confidence_score,
            risk_level=risk_level,
            time_horizon="short_term",
            overall_score=overall_score,
            technical_score=technical_score,
            financial_score=financial_score,
            market_activity_score=activity_score,
            current_price=technical.current_price,
            nearest_support=technical.nearest_support,
            nearest_resistance=technical.nearest_resistance,
            reasons=reasons,
            calculated_at=datetime.now(timezone.utc),
        )

    def _calculate_technical_score(
        self,
        snapshot: TechnicalAnalysisSnapshot,
    ) -> tuple[int, list[AnalysisReason]]:
        score = 50
        reasons: list[AnalysisReason] = []

        signal_adjustments = {
            TechnicalSignal.STRONG_BUY: 28,
            TechnicalSignal.BUY: 16,
            TechnicalSignal.NEUTRAL: 0,
            TechnicalSignal.SELL: -16,
            TechnicalSignal.STRONG_SELL: -28,
        }

        score += signal_adjustments[snapshot.signal]

        if snapshot.trend is TrendDirection.BULLISH:
            score += 10
            reasons.append(
                AnalysisReason(
                    category="Trend",
                    reason_type=AnalysisReasonType.POSITIVE,
                    message="The prevailing technical trend is bullish.",
                )
            )
        elif snapshot.trend is TrendDirection.BEARISH:
            score -= 10
            reasons.append(
                AnalysisReason(
                    category="Trend",
                    reason_type=AnalysisReasonType.NEGATIVE,
                    message="The prevailing technical trend is bearish.",
                )
            )
        else:
            reasons.append(
                AnalysisReason(
                    category="Trend",
                    reason_type=AnalysisReasonType.NEUTRAL,
                    message="The technical trend is currently neutral.",
                )
            )

        if snapshot.rsi_14 is not None:
            if Decimal("45") <= snapshot.rsi_14 <= Decimal("65"):
                score += 5
                reasons.append(
                    AnalysisReason(
                        category="Momentum",
                        reason_type=AnalysisReasonType.POSITIVE,
                        message=(
                            "RSI shows constructive momentum without "
                            "being deeply overbought."
                        ),
                    )
                )
            elif snapshot.rsi_14 >= Decimal("75"):
                score -= 6
                reasons.append(
                    AnalysisReason(
                        category="Momentum",
                        reason_type=AnalysisReasonType.NEGATIVE,
                        message=(
                            "RSI is elevated, increasing the risk of "
                            "short-term exhaustion."
                        ),
                    )
                )
            elif snapshot.rsi_14 <= Decimal("30"):
                score -= 3
                reasons.append(
                    AnalysisReason(
                        category="Momentum",
                        reason_type=AnalysisReasonType.NEGATIVE,
                        message=(
                            "RSI reflects weak momentum and an "
                            "oversold market condition."
                        ),
                    )
                )

        if (
            snapshot.sma_20 is not None
            and snapshot.current_price > snapshot.sma_20
        ):
            score += 4
            reasons.append(
                AnalysisReason(
                    category="Price structure",
                    reason_type=AnalysisReasonType.POSITIVE,
                    message="Price is trading above its 20-day average.",
                )
            )

        if (
            snapshot.sma_50 is not None
            and snapshot.current_price < snapshot.sma_50
        ):
            score -= 4
            reasons.append(
                AnalysisReason(
                    category="Price structure",
                    reason_type=AnalysisReasonType.NEGATIVE,
                    message="Price is trading below its 50-day average.",
                )
            )

        return self._clamp(score), reasons

    def _calculate_financial_score(
        self,
        snapshot: FinancialHealthSnapshot | None,
    ) -> tuple[int, list[AnalysisReason]]:
        if snapshot is None:
            return (
                50,
                [
                    AnalysisReason(
                        category="Financial health",
                        reason_type=AnalysisReasonType.NEUTRAL,
                        message=(
                            "Financial-health data was unavailable, so "
                            "the financial contribution remains neutral."
                        ),
                    )
                ],
            )

        score = self._clamp(snapshot.overall_score)

        if snapshot.rating in {
            FinancialHealthRating.STRONG,
            FinancialHealthRating.HEALTHY,
        }:
            reason_type = AnalysisReasonType.POSITIVE
            message = (
                f"Financial health is rated "
                f"{snapshot.rating.value.replace('_', ' ')}."
            )
        elif snapshot.rating in {
            FinancialHealthRating.WEAK,
            FinancialHealthRating.HIGH_RISK,
        }:
            reason_type = AnalysisReasonType.NEGATIVE
            message = (
                f"Financial health is rated "
                f"{snapshot.rating.value.replace('_', ' ')}."
            )
        else:
            reason_type = AnalysisReasonType.NEUTRAL
            message = "Financial health presents a mixed picture."

        return (
            score,
            [
                AnalysisReason(
                    category="Financial health",
                    reason_type=reason_type,
                    message=message,
                )
            ],
        )

    def _calculate_activity_score(
        self,
        snapshot: TechnicalAnalysisSnapshot,
    ) -> tuple[int, list[AnalysisReason]]:
        score = 50
        reasons: list[AnalysisReason] = []

        if snapshot.volume_ratio is not None:
            if snapshot.volume_ratio >= Decimal("1.50"):
                if snapshot.price_change is not None:
                    if snapshot.price_change > 0:
                        score += 25
                        reason_type = AnalysisReasonType.POSITIVE
                        message = (
                            "Price strength is supported by "
                            "above-average trading volume."
                        )
                    elif snapshot.price_change < 0:
                        score -= 25
                        reason_type = AnalysisReasonType.NEGATIVE
                        message = (
                            "Selling pressure is occurring on "
                            "above-average trading volume."
                        )
                    else:
                        reason_type = AnalysisReasonType.NEUTRAL
                        message = (
                            "Trading volume is elevated while price "
                            "remains broadly unchanged."
                        )
                else:
                    score += 5
                    reason_type = AnalysisReasonType.NEUTRAL
                    message = "Trading activity is above its recent average."

                reasons.append(
                    AnalysisReason(
                        category="Market activity",
                        reason_type=reason_type,
                        message=message,
                    )
                )
            elif snapshot.volume_ratio <= Decimal("0.60"):
                score -= 5
                reasons.append(
                    AnalysisReason(
                        category="Market activity",
                        reason_type=AnalysisReasonType.NEUTRAL,
                        message=(
                            "Current participation is below its recent "
                            "average."
                        ),
                    )
                )

        return self._clamp(score), reasons

    def _weighted_score(
        self,
        *,
        technical_score: int,
        financial_score: int,
        activity_score: int,
    ) -> int:
        weighted = (
            Decimal(technical_score) * self._TECHNICAL_WEIGHT
            + Decimal(financial_score) * self._FINANCIAL_WEIGHT
            + Decimal(activity_score) * self._ACTIVITY_WEIGHT
        )

        return self._clamp(int(weighted.quantize(Decimal("1"))))

    @staticmethod
    def _probability_from_score(score: int) -> int:
        # Deliberately compress extremes: deterministic signals must
        # never present themselves as near-certainty.
        probability = 50 + round((score - 50) * 0.72)
        return max(15, min(85, probability))

    @staticmethod
    def _outlook(score: int) -> StockOutlook:
        if score >= 60:
            return StockOutlook.BULLISH
        if score <= 40:
            return StockOutlook.BEARISH
        return StockOutlook.NEUTRAL

    @staticmethod
    def _confidence_score(
        *,
        overall_score: int,
        technical: TechnicalAnalysisSnapshot,
        financial_available: bool,
    ) -> int:
        distance_from_neutral = abs(overall_score - 50)
        confidence = 45 + min(30, distance_from_neutral)

        available_indicators = sum(
            value is not None
            for value in (
                technical.sma_20,
                technical.sma_50,
                technical.rsi_14,
                technical.macd,
                technical.atr_14,
                technical.volume_ratio,
            )
        )

        confidence += min(12, available_indicators * 2)

        if financial_available:
            confidence += 8

        return max(35, min(90, confidence))

    @staticmethod
    def _risk_level(
        *,
        technical: TechnicalAnalysisSnapshot,
        overall_score: int,
        technical_score: int,
        financial_score: int,
        financial_available: bool,
    ) -> StockRiskLevel:
        risk_points = 0

        if technical.atr_14 is not None:
            atr_percent = (
                technical.atr_14 / technical.current_price
            ) * Decimal("100")

            if atr_percent >= Decimal("5"):
                risk_points += 2
            elif atr_percent >= Decimal("3"):
                risk_points += 1

        if abs(technical_score - financial_score) >= 30:
            risk_points += 1

        if not financial_available:
            risk_points += 1

        if 43 <= overall_score <= 57:
            risk_points += 1

        if risk_points >= 3:
            return StockRiskLevel.HIGH

        if risk_points >= 1:
            return StockRiskLevel.MEDIUM

        return StockRiskLevel.LOW

    @staticmethod
    def _clamp(value: int) -> int:
        return max(0, min(100, value))
