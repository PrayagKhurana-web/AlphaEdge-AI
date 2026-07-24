"""
Adapter connecting quant_engine to the existing stock_history module.

This is an application-to-application adapter, not an infrastructure
provider: it never calls Yahoo Finance, issues an HTTP request, or
duplicates any provider logic. stock_history remains the sole owner of
historical candle retrieval -- this file only satisfies quant_engine's
own HistoricalDataProviderPort by delegating to stock_history's already
-existing HistoricalDataService, so quant_engine's application layer
never has to depend on stock_history's infrastructure or API layers.
"""

from app.modules.quant_engine.application.ports import HistoricalDataProviderPort
from app.modules.stock_history.application.services import HistoricalDataService
from app.modules.stock_history.domain.entities import HistoricalSeries


class StockHistoryServiceAdapter(HistoricalDataProviderPort):
    """
    HistoricalDataProviderPort implementation backed by stock_history's
    own HistoricalDataService.

    This class performs no calculation, no symbol conversion, and no
    candle mutation -- it is a thin pass-through to stock_history's
    existing application service, returning its HistoricalSeries
    unchanged.
    """

    def __init__(self, stock_history_service: HistoricalDataService) -> None:
        """
        Args:
            stock_history_service: The existing stock_history
                HistoricalDataService instance to delegate to.
        """
        self._stock_history_service = stock_history_service

    async def get_history(
        self,
        display_symbol: str,
        *,
        interval: str,
        period: str,
    ) -> HistoricalSeries:
        """
        Retrieves a historical candle series via stock_history's own
        HistoricalDataService.

        Args:
            display_symbol: The public display symbol, passed through
                unchanged -- no Yahoo-specific or other provider-specific
                symbol conversion happens in this adapter.
            interval: Passed through unchanged to HistoricalDataService.
            period: Passed through unchanged to HistoricalDataService.

        Returns:
            The HistoricalSeries produced by HistoricalDataService,
            returned exactly as received -- not reconstructed, copied,
            sorted, deduplicated, or otherwise mutated.

        Raises:
            Whatever domain exceptions HistoricalDataService.get_history
            raises (e.g. stock_history's own invalid-request, invalid-
            data, timeout, unavailable, or rate-limited exceptions).
            This adapter does not catch or translate them -- they
            propagate unchanged so the quant_engine application service
            and, ultimately, its API layer can handle them.
        """
        return await self._stock_history_service.get_history(
            display_symbol,
            period=period,
            interval=interval,
        )