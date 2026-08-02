from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.modules.multibagger.api.dependencies import (
    get_multibagger_potential_service,
    get_multibagger_ranking_service,
)
from app.modules.multibagger.domain.entities import (
    MultibaggerObservation,
    MultibaggerObservationType,
    MultibaggerPotentialCategory,
    MultibaggerPotentialSnapshot,
)
from app.modules.multibagger.domain.rankings import (
    MultibaggerRankingsSnapshot,
)


NOW = datetime(2026, 8, 3, tzinfo=timezone.utc)


def make_snapshot(
    symbol: str = "TEST.NSE",
) -> MultibaggerPotentialSnapshot:
    return MultibaggerPotentialSnapshot(
        symbol=symbol.split(".")[0],
        display_symbol=symbol,
        company_name="Test Limited",
        potential_score=76,
        potential_category=(
            MultibaggerPotentialCategory.HIGH
        ),
        growth_quality_score=82,
        financial_strength_score=80,
        valuation_attractiveness_score=65,
        momentum_score=74,
        risk_quality_score=72,
        data_completeness_score=92,
        market_cap=Decimal("50000000000"),
        revenue_growth=Decimal("0.20"),
        earnings_growth=Decimal("0.25"),
        return_on_equity=Decimal("0.18"),
        debt_to_equity=Decimal("0.40"),
        trailing_pe=Decimal("24"),
        price_to_book=Decimal("3.2"),
        observations=(
            MultibaggerObservation(
                category="growth",
                observation_type=(
                    MultibaggerObservationType.POSITIVE
                ),
                message="Growth indicators are strong.",
            ),
        ),
        calculated_at=NOW,
    )


class PotentialService:
    async def analyse_stock(
        self,
        display_symbol: str,
        **kwargs,
    ):
        return make_snapshot(display_symbol.upper())


class RankingService:
    async def get_rankings(self, **kwargs):
        return MultibaggerRankingsSnapshot(
            rankings=(make_snapshot("TEST.NSE"),),
            failed_symbols=("FAIL.NSE",),
            universe_size=2,
            successful_count=1,
            minimum_score=kwargs["minimum_score"],
            result_limit=kwargs["limit"],
            generated_at=NOW,
            cache_expires_at=NOW + timedelta(minutes=5),
        )


@pytest_asyncio.fixture
async def client():
    app.dependency_overrides[
        get_multibagger_potential_service
    ] = lambda: PotentialService()

    app.dependency_overrides[
        get_multibagger_ranking_service
    ] = lambda: RankingService()

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_single_stock_endpoint(
    client: AsyncClient,
) -> None:
    response = await client.get(
        "/api/v1/multibagger/TEST.NSE"
    )

    assert response.status_code == 200

    body = response.json()

    assert body["displaySymbol"] == "TEST.NSE"
    assert body["potentialScore"] == 76
    assert body["potentialCategory"] == "high"
    assert body["disclaimer"]


@pytest.mark.asyncio
async def test_rankings_endpoint(
    client: AsyncClient,
) -> None:
    response = await client.get(
        "/api/v1/multibagger/rankings",
        params={
            "minimumScore": 60,
            "limit": 5,
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["returnedCount"] == 1
    assert body["failedSymbols"] == ["FAIL.NSE"]
    assert body["minimumScore"] == 60
    assert body["weights"]["growth"] == 30


@pytest.mark.asyncio
async def test_rankings_reject_invalid_limit(
    client: AsyncClient,
) -> None:
    response = await client.get(
        "/api/v1/multibagger/rankings",
        params={"limit": 0},
    )

    assert response.status_code == 422
