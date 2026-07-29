from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db_session
from app.modules.portfolio.application.service import PortfolioService
from app.modules.portfolio.infrastructure.repository import (
    SqlAlchemyPortfolioRepository,
)
from app.modules.stock_details.api.dependencies import (
    StockQuoteServiceDependency,
)


DatabaseSessionDependency = Annotated[
    AsyncSession,
    Depends(get_db_session),
]


async def get_portfolio_service(
    session: DatabaseSessionDependency,
    quote_service: StockQuoteServiceDependency,
) -> PortfolioService:
    repository = SqlAlchemyPortfolioRepository(session)

    return PortfolioService(
        repository=repository,
        session=session,
        quote_service=quote_service,
    )


PortfolioServiceDependency = Annotated[
    PortfolioService,
    Depends(get_portfolio_service),
]
