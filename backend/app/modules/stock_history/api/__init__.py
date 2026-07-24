"""Public HTTP interface for the stock_history module.

Exposes the module's FastAPI ``router`` along with its public response
schemas (``HistoricalCandleResponse``, ``HistoricalSeriesResponse``) for
use by the rest of the application. Internal wiring — dependencies,
application services, providers, domain objects, and exceptions — is
intentionally not re-exported here.
"""

from .routes import router
from .schemas import HistoricalCandleResponse, HistoricalSeriesResponse

__all__ = [
    "router",
    "HistoricalCandleResponse",
    "HistoricalSeriesResponse",
]