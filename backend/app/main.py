from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.modules.market_data.api.dependencies import market_data_lifespan
from app.modules.market_data.api.routes import router as market_data_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Application-wide lifespan, composed from each mounted module's own
    lifespan context manager. Currently only market_data contributes a
    lifespan (its shared httpx.AsyncClient must be created at startup and
    closed at shutdown); future modules that need startup/shutdown
    handling are expected to nest their own lifespan context managers
    inside this function in the same way, rather than each defining a
    separate, uncomposed lifespan on the app.
    """
    async with market_data_lifespan(app):
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


@app.get("/api/v1/health", tags=["System"])
async def health_check() -> dict[str, str]:
    """Return the current health status of the API."""
    return {
        "status": "healthy",
        "service": "AlphaEdge AI API",
        "version": "0.1.0",
    }