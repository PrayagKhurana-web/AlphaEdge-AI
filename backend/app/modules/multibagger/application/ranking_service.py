"""Cached ranked-universe Multibagger screening."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.modules.multibagger.application.services import (
    MultibaggerPotentialService,
)
from app.modules.multibagger.domain.entities import (
    MultibaggerPotentialSnapshot,
)
from app.modules.multibagger.domain.exceptions import (
    InvalidMultibaggerRequestError,
)
from app.modules.multibagger.domain.rankings import (
    MultibaggerRankingsSnapshot,
)


@dataclass(frozen=True, slots=True)
class _RankingCacheEntry:
    rankings: tuple[MultibaggerPotentialSnapshot, ...]
    failed_symbols: tuple[str, ...]
    generated_at: datetime
    cache_expires_at: datetime


class MultibaggerRankingService:
    """Screen, rank and cache a configured stock universe."""

    def __init__(
        self,
        *,
        potential_service: MultibaggerPotentialService,
        ranking_universe: tuple[str, ...],
        cache_ttl_seconds: int,
        max_concurrency: int,
    ) -> None:
        normalized_universe = tuple(
            symbol.strip().upper()
            for symbol in ranking_universe
            if symbol.strip()
        )

        if not normalized_universe:
            raise ValueError(
                "Multibagger ranking universe must not be empty."
            )

        if len(normalized_universe) != len(set(normalized_universe)):
            raise ValueError(
                "Multibagger ranking universe contains duplicates."
            )

        if cache_ttl_seconds <= 0:
            raise ValueError(
                "Multibagger cache TTL must be positive."
            )

        if max_concurrency <= 0:
            raise ValueError(
                "Multibagger concurrency must be positive."
            )

        self._potential_service = potential_service
        self._ranking_universe = normalized_universe
        self._cache_ttl_seconds = cache_ttl_seconds
        self._max_concurrency = max_concurrency

        self._cache: dict[
            tuple[str, str, str],
            _RankingCacheEntry,
        ] = {}

        self._lock = asyncio.Lock()

    async def get_rankings(
        self,
        *,
        minimum_score: int = 0,
        limit: int = 10,
        interval: str = "1d",
        technical_period: str = "1y",
        financial_period: str = "annual",
    ) -> MultibaggerRankingsSnapshot:
        if not 0 <= minimum_score <= 100:
            raise InvalidMultibaggerRequestError(
                "minimum_score must be between zero and 100."
            )

        if not 1 <= limit <= 100:
            raise InvalidMultibaggerRequestError(
                "limit must be between one and 100."
            )

        cache_key = (
            interval.strip().lower(),
            technical_period.strip().lower(),
            financial_period.strip().lower(),
        )

        entry = await self._get_or_build_entry(
            cache_key=cache_key,
            interval=interval,
            technical_period=technical_period,
            financial_period=financial_period,
        )

        filtered = tuple(
            snapshot
            for snapshot in entry.rankings
            if snapshot.potential_score >= minimum_score
        )[:limit]

        return MultibaggerRankingsSnapshot(
            rankings=filtered,
            failed_symbols=entry.failed_symbols,
            universe_size=len(self._ranking_universe),
            successful_count=len(entry.rankings),
            minimum_score=minimum_score,
            result_limit=limit,
            generated_at=entry.generated_at,
            cache_expires_at=entry.cache_expires_at,
        )

    async def _get_or_build_entry(
        self,
        *,
        cache_key: tuple[str, str, str],
        interval: str,
        technical_period: str,
        financial_period: str,
    ) -> _RankingCacheEntry:
        now = datetime.now(timezone.utc)
        cached = self._cache.get(cache_key)

        if cached is not None and cached.cache_expires_at > now:
            return cached

        async with self._lock:
            now = datetime.now(timezone.utc)
            cached = self._cache.get(cache_key)

            if cached is not None and cached.cache_expires_at > now:
                return cached

            semaphore = asyncio.Semaphore(
                self._max_concurrency
            )

            async def analyse(
                display_symbol: str,
            ) -> tuple[
                str,
                MultibaggerPotentialSnapshot | None,
            ]:
                async with semaphore:
                    try:
                        result = await self._potential_service.analyse_stock(
                            display_symbol,
                            interval=interval,
                            technical_period=technical_period,
                            financial_period=financial_period,
                        )
                    except Exception:
                        return display_symbol, None

                    return display_symbol, result

            results = await asyncio.gather(
                *(
                    analyse(display_symbol)
                    for display_symbol in self._ranking_universe
                )
            )

            successful = [
                result
                for _, result in results
                if result is not None
            ]

            successful.sort(
                key=lambda result: (
                    -result.potential_score,
                    -result.data_completeness_score,
                    -result.financial_strength_score,
                    -result.growth_quality_score,
                    result.display_symbol,
                )
            )

            failed_symbols = tuple(
                display_symbol
                for display_symbol, result in results
                if result is None
            )

            generated_at = datetime.now(timezone.utc)

            entry = _RankingCacheEntry(
                rankings=tuple(successful),
                failed_symbols=failed_symbols,
                generated_at=generated_at,
                cache_expires_at=(
                    generated_at
                    + timedelta(
                        seconds=self._cache_ttl_seconds
                    )
                ),
            )

            self._cache[cache_key] = entry
            return entry

    async def clear_cache(self) -> None:
        async with self._lock:
            self._cache.clear()
