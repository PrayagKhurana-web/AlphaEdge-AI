"""Application service for the company_fundamentals module.

Orchestrates retrieval of a company's fundamentals snapshot by delegating
to a ``FundamentalsProviderPort`` implementation. This layer deliberately
contains no normalization, formatting, scaling, or transport concerns —
those belong to the infrastructure and API layers respectively. Domain
exceptions raised by the provider are left to propagate unchanged so the
API layer can translate them into HTTP responses.
"""

from ..domain.entities import CompanyFundamentals
from .ports import FundamentalsProviderPort


class CompanyFundamentalsService:
    """Orchestrates company fundamentals retrieval via a provider port."""

    def __init__(self, provider: FundamentalsProviderPort) -> None:
        self._provider = provider

    async def get_fundamentals(
        self,
        display_symbol: str,
    ) -> CompanyFundamentals:
        """Retrieve a company's fundamentals snapshot.

        Delegates directly to the configured provider and returns the
        resulting ``CompanyFundamentals`` unchanged. This method performs
        orchestration only — normalization, transport, and formatting
        concerns are deliberately left outside the application layer, and
        any domain exceptions raised by the provider propagate unchanged.
        """
        return await self._provider.get_fundamentals(display_symbol)