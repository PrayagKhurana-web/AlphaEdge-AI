from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="AlphaEdge AI API",
    description="Backend API for the AlphaEdge AI stock intelligence platform.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/v1/health", tags=["System"])
async def health_check() -> dict[str, str]:
    """Return the current health status of the API."""
    return {
        "status": "healthy",
        "service": "AlphaEdge AI API",
        "version": "0.1.0",
    }