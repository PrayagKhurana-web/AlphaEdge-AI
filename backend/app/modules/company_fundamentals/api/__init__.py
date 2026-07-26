"""Public HTTP interface for the company_fundamentals module.

Exposes the module's FastAPI ``router`` along with its public response
schema (``CompanyFundamentalsResponse``) for use by the rest of the
application. Internal wiring — dependencies, application services,
providers, domain objects, and exceptions — is intentionally not
re-exported here.
"""

from .routes import router
from .schemas import CompanyFundamentalsResponse

__all__ = [
    "router",
    "CompanyFundamentalsResponse",
]