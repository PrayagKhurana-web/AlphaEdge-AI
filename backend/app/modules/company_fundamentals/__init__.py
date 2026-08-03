"""Public entry point for the company_fundamentals module.

Exposes the module's FastAPI ``router`` for registration with the
application. No other internals — dependencies, schemas, services,
providers, domain entities, or exceptions — are re-exported here.
"""

from .api import router

__all__ = [
    "router",
]