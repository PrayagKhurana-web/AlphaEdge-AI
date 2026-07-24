from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.modules.company_fundamentals.api.dependencies import (
    company_fundamentals_lifespan,
)
from app.modules.company_fundamentals.api.routes import (
    router as company_fundamentals_router,
)
from app.modules.market_data.api.dependencies import market_data_lifespan
from app.modules.market_data.api.routes import router as market_data_router
from app.modules.quant_engine.api.dependencies import quant_engine_lifespan
from app.modules.quant_engine.api.routes import router as quant_engine_router
from app.modules.stock_details.api.dependencies import stock_details_lifespan
from app.modules.stock_details.api.routes import router as stock_details_router
from app.modules.stock_history.api.dependencies import stock_history_lifespan
from app.modules.stock_history.api.routes import router as stock_history_router
from app.modules.stock_search.api.dependencies import stock_search_lifespan
from app.modules.stock_search.api.routes import router as stock_search_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Application-wide lifespan, composed from each mounted module's own
    lifespan context manager. market_data, stock_search, stock_details,
    stock_history, company_fundamentals, and quant_engine each
    contribute their own startup and shutdown handling. Modules that
    own shared resources create and close them within their lifespans,
    while quant_engine initializes and resets its own dependency
    singletons while reusing stock_history's managed historical-data
    service.

    Future modules that require startup or shutdown handling should nest
    their own lifespan context managers inside this function in the same
    way, rather than defining separate, uncomposed application
    lifespans.
    """
    async with market_data_lifespan(app):
        async with stock_search_lifespan(app):
            async with stock_details_lifespan(app):
                async with stock_history_lifespan(app):
                    async with company_fundamentals_lifespan(app):
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

app.include_router(market_data_router)
app.include_router(stock_search_router)
app.include_router(stock_details_router)
app.include_router(stock_history_router)
app.include_router(company_fundamentals_router)
app.include_router(quant_engine_router)


@app.get("/api/v1/health", tags=["System"])
async def health_check() -> dict[str, str]:
    """Return the current health status of the API."""
    return {
        "status": "healthy",
        "service": "AlphaEdge AI API",
        "version": "0.1.0",
    }