"""Application service for combined stock analysis."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from app.modules.stock_analysis.application.ports import (
    FinancialHealthProviderPort,
    StockAnalysisCalculatorPort,
    TechnicalAnalysisProviderPort,
)
from app.modules.stock_analysis.domain.entities import (
    StockAnalysisSnapshot,
    StockOutlook,
    TopPicksSnapshot,
)


class StockAnalysisService:
    """Orchestrate individual analysis and cached Top Picks."""

    def __init__(
        self,
        technical_provider: TechnicalAnalysisProviderPort,
        financial_provider: FinancialHealthProviderPort,
        calculator: StockAnalysisCalculatorPort,
        *,
        top_picks_universe: tuple[str, ...],
        top_picks_cache_ttl_seconds: int,
        top_picks_max_concurrency: int,
    ) -> None:
        if not top_picks_universe:
            raise ValueError(
                "Top Picks universe must not be empty."
            )

        if top_picks_cache_ttl_seconds <= 0:
            raise ValueError(
                "Top Picks cache TTL must be positive."
            )

        if top_picks_max_concurrency <= 0:
            raise ValueError(
                "Top Picks concurrency must be positive."
            )

        self._technical_provider = technical_provider
        self._financial_provider = financial_provider
        self._calculator = calculator

        self._top_picks_universe = top_picks_universe
        self._top_picks_cache_ttl_seconds = (
            top_picks_cache_ttl_seconds
        )
        self._top_picks_max_concurrency = (
            top_picks_max_concurrency
        )

        self._top_picks_cache: TopPicksSnapshot | None = None
        self._top_picks_lock = asyncio.Lock()

    async def get_stock_analysis(
        self,
        display_symbol: str,
        *,
        interval: str = "1d",
        technical_period: str = "1y",
        financial_period: str = "annual",
    ) -> StockAnalysisSnapshot:
        normalized_symbol = display_symbol.strip()

        if not normalized_symbol:
            raise ValueError("Display symbol is required.")

        technical = (
            await self._technical_provider.get_technical_analysis(
                normalized_symbol,
                interval=interval,
                period=technical_period,
            )
        )

        financial = None

        try:
            financial = (
                await self._financial_provider.get_financial_health(
                    normalized_symbol,
                    period=financial_period,
                )
            )
        except Exception:
            # A valid technical outlook remains useful when
            # financial data is temporarily unavailable.
            financial = None

        return self._calculator.calculate_snapshot(
            technical,
            financial,
        )

    async def get_top_picks(
        self,
        *,
        interval: str = "1d",
        technical_period: str = "1y",
        financial_period: str = "annual",
    ) -> TopPicksSnapshot:
        now = datetime.now(timezone.utc)

        if (
            self._top_picks_cache is not None
            and self._top_picks_cache.cache_expires_at > now
        ):
            return self._top_picks_cache

        async with self._top_picks_lock:
            now = datetime.now(timezone.utc)

            if (
                self._top_picks_cache is not None
                and self._top_picks_cache.cache_expires_at > now
            ):
                return self._top_picks_cache

            semaphore = asyncio.Semaphore(
                self._top_picks_max_concurrency
            )

            async def analyse_symbol(
                display_symbol: str,
            ) -> tuple[
                str,
                StockAnalysisSnapshot | None,
            ]:
                async with semaphore:
                    try:
                        snapshot = await self.get_stock_analysis(
                            display_symbol,
                            interval=interval,
                            technical_period=technical_period,
                            financial_period=financial_period,
                        )
                    except Exception:
                        return display_symbol, None

                    return display_symbol, snapshot

            results = await asyncio.gather(
                *(
                    analyse_symbol(display_symbol)
                    for display_symbol in self._top_picks_universe
                )
            )

            successful = [
                snapshot
                for _, snapshot in results
                if snapshot is not None
            ]

            failed_symbols = tuple(
                display_symbol
                for display_symbol, snapshot in results
                if snapshot is None
            )

            ranked_picks = tuple(
                sorted(
                    (
                        snapshot
                        for snapshot in successful
                        if snapshot.outlook
                        is not StockOutlook.BEARISH
                    ),
                    key=lambda snapshot: (
                        snapshot.overall_score,
                        snapshot.confidence_score,
                        snapshot.bullish_probability,
                    ),
                    reverse=True,
                )
            )

            generated_at = datetime.now(timezone.utc)

            snapshot = TopPicksSnapshot(
                picks=ranked_picks,
                failed_symbols=failed_symbols,
                universe_size=len(self._top_picks_universe),
                successful_count=len(successful),
                generated_at=generated_at,
                cache_expires_at=(
                    generated_at
                    + timedelta(
                        seconds=(
                            self._top_picks_cache_ttl_seconds
                        )
                    )
                ),
            )

            self._top_picks_cache = snapshot
            return snapshot

    async def clear_top_picks_cache(self) -> None:
        async with self._top_picks_lock:
            self._top_picks_cache = None
