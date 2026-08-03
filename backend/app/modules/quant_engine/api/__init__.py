"""Public HTTP interface for the quant_engine module.

Exposes the module's FastAPI ``router`` along with its public response
schema (``TechnicalAnalysisSnapshotResponse``) for use by the rest of
the application. Internal wiring — dependencies, application services,
infrastructure adapters/calculators, domain objects, and exceptions — is
intentionally not re-exported here.
"""

from .routes import router
from .schemas import TechnicalAnalysisSnapshotResponse

__all__ = [
    "router",
    "TechnicalAnalysisSnapshotResponse",
]