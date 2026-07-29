from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.modules.auth.api.routes import router as auth_router

from app.modules.company_fundamentals.api.dependencies import (
    company_fundamentals_lifespan,
)
from app.modules.company_fundamentals.api.routes import (
    router as company_fundamentals_router,
)
from app.modules.financial_health.api.dependencies import (
    financial_health_lifespan,
)
from app.modules.financial_health.api.routes import (
    router as financial_health_router,
)
from app.modules.financial_statements.api.dependencies import (
    financial_statements_lifespan,
)
from app.modules.financial_statements.api.routes import (
    router as financial_statements_router,
)
from app.modules.market_data.api.dependencies import market_data_lifespan
from app.modules.market_data.api.routes import router as market_data_router
from app.modules.portfolio.api.routes import router as portfolio_router
from app.modules.quant_engine.api.dependencies import quant_engine_lifespan
from app.modules.quant_engine.api.routes import router as quant_engine_router
from app.modules.stock_details.api.dependencies import stock_details_lifespan
from app.modules.stock_details.api.routes import router as stock_details_router
from app.modules.stock_history.api.dependencies import stock_history_lifespan
from app.modules.stock_history.api.routes import router as stock_history_router
from app.modules.stock_search.api.dependencies import stock_search_lifespan
from app.modules.stock_search.api.routes import router as stock_search_router
from app.modules.watchlist.api.routes import router as watchlist_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Application-wide lifespan composed from each mounted module's own
    lifespan context manager.
    """
    async with market_data_lifespan(app):
        async with stock_search_lifespan(app):
            async with stock_details_lifespan(app):
                async with stock_history_lifespan(app):
                    async with company_fundamentals_lifespan(app):
                        async with financial_statements_lifespan(app):
                            async with financial_health_lifespan(app):
                                async with quant_engine_lifespan(app):
                                    yield


app = FastAPI(
    title="AlphaEdge AI API",
    description="Backend API for the AlphaEdge AI stock intelligence platform.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(market_data_router)
app.include_router(portfolio_router)
app.include_router(stock_search_router)
app.include_router(stock_details_router)
app.include_router(stock_history_router)
app.include_router(company_fundamentals_router)
app.include_router(financial_statements_router)
app.include_router(financial_health_router)
app.include_router(quant_engine_router)
app.include_router(watchlist_router)


@app.get("/api/v1/health", tags=["System"])
async def health_check() -> dict[str, str]:
    """Return the current health status of the API."""
    return {
        "status": "healthy",
        "service": "AlphaEdge AI API",
        "version": "0.1.0",
    }
