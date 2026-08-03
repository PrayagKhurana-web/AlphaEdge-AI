"""FastAPI dependency wiring for the watchlist module."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db_session
from app.modules.watchlist.application.service import WatchlistService
from app.modules.watchlist.infrastructure.repository import (
    SqlAlchemyWatchlistRepository,
)


DatabaseSessionDependency = Annotated[
    AsyncSession,
    Depends(get_db_session),
]


async def get_watchlist_service(
    session: DatabaseSessionDependency,
) -> WatchlistService:
    """Create a request-scoped watchlist service."""

    repository = SqlAlchemyWatchlistRepository(session)

    return WatchlistService(
        repository=repository,
        session=session,
    )


WatchlistServiceDependency = Annotated[
    WatchlistService,
    Depends(get_watchlist_service),
]
