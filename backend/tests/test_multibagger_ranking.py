import pytest

from app.modules.multibagger.application.ranking_service import (
    MultibaggerRankingService,
)
from app.modules.multibagger.domain.exceptions import (
    InvalidMultibaggerRequestError,
)


class Result:
    def __init__(
        self,
        symbol: str,
        score: int,
        completeness: int,
        financial: int,
        growth: int,
    ) -> None:
        self.display_symbol = symbol
        self.potential_score = score
        self.data_completeness_score = completeness
        self.financial_strength_score = financial
        self.growth_quality_score = growth


class StubPotentialService:
    def __init__(self) -> None:
        self.calls = 0

    async def analyse_stock(
        self,
        display_symbol: str,
        **kwargs,
    ):
        self.calls += 1

        if display_symbol == "FAIL.NSE":
            raise RuntimeError("unavailable")

        scores = {
            "AAA.NSE": (70, 95, 80, 75),
            "BBB.NSE": (85, 90, 78, 88),
            "CCC.NSE": (55, 100, 90, 60),
        }

        return Result(
            display_symbol,
            *scores[display_symbol],
        )


@pytest.mark.asyncio
async def test_rankings_are_sorted_and_failures_reported() -> None:
    potential = StubPotentialService()

    service = MultibaggerRankingService(
        potential_service=potential,
        ranking_universe=(
            "AAA.NSE",
            "BBB.NSE",
            "CCC.NSE",
            "FAIL.NSE",
        ),
        cache_ttl_seconds=300,
        max_concurrency=2,
    )

    result = await service.get_rankings(limit=10)

    assert [
        item.display_symbol
        for item in result.rankings
    ] == [
        "BBB.NSE",
        "AAA.NSE",
        "CCC.NSE",
    ]

    assert result.failed_symbols == ("FAIL.NSE",)
    assert result.successful_count == 3


@pytest.mark.asyncio
async def test_minimum_score_and_limit_are_applied() -> None:
    service = MultibaggerRankingService(
        potential_service=StubPotentialService(),
        ranking_universe=(
            "AAA.NSE",
            "BBB.NSE",
            "CCC.NSE",
        ),
        cache_ttl_seconds=300,
        max_concurrency=2,
    )

    result = await service.get_rankings(
        minimum_score=60,
        limit=1,
    )

    assert len(result.rankings) == 1
    assert result.rankings[0].display_symbol == "BBB.NSE"


@pytest.mark.asyncio
async def test_rankings_use_cache() -> None:
    potential = StubPotentialService()

    service = MultibaggerRankingService(
        potential_service=potential,
        ranking_universe=("AAA.NSE", "BBB.NSE"),
        cache_ttl_seconds=300,
        max_concurrency=2,
    )

    await service.get_rankings()
    await service.get_rankings(minimum_score=60)

    assert potential.calls == 2


@pytest.mark.asyncio
async def test_invalid_minimum_score_is_rejected() -> None:
    service = MultibaggerRankingService(
        potential_service=StubPotentialService(),
        ranking_universe=("AAA.NSE",),
        cache_ttl_seconds=300,
        max_concurrency=1,
    )

    with pytest.raises(
        InvalidMultibaggerRequestError,
        match="minimum_score",
    ):
        await service.get_rankings(minimum_score=101)
