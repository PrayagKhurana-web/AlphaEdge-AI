"""Public entry point for the quant_engine module.

Exposes the module's FastAPI ``router`` for registration with the
application. No other internals — dependencies, schemas, services,
infrastructure adapters/calculators, domain entities, or exceptions —
are re-exported here.
"""

from .api import router

__all__ = [
    "router",
]