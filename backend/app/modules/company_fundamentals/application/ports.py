"""Application-layer provider port for the company_fundamentals module.

The application layer depends only on this abstraction, never on a
concrete data source. Infrastructure providers (e.g. a Yahoo Finance
adapter) implement this port, which keeps Yahoo Finance, HTTP, and any
other transport-level concerns entirely outside the application and
domain layers.
"""

from typing import Protocol

from app.modules.company_fundamentals.domain.entities import CompanyFundamentals


class FundamentalsProviderPort(Protocol):
    """Abstraction for retrieving company fundamentals from a data source."""

    async def get_fundamentals(
        self,
        display_symbol: str,
    ) -> CompanyFundamentals:
        """Retrieve a point-in-time fundamentals snapshot for a symbol.

        ``display_symbol`` is the normalized public symbol already
        accepted by the API layer. The returned ``CompanyFundamentals``
        is a scalar, point-in-time snapshot, so provider ordering,
        formatting, scaling, or derived calculations do not apply here.
        Any field the underlying data source does not supply must be
        represented as ``None`` within the returned entity rather than
        omitted, zeroed, or estimated.

        Implementations may raise the approved company_fundamentals
        domain exceptions to signal invalid requests, unusable provider
        data, or provider unavailability, timeouts, and rate limiting.
        """
        ...