"""
Application-layer port (abstract interface) for the stock_history module.

A "port" here is a contract the application layer depends on but does not
implement -- concrete implementations live in infrastructure/ and are
wired in via dependency injection. This is what lets the historical data
backend (Yahoo Finance today, or a future replacement) change without any
change to application/services.py or the API layer that depends on it.

An ABC is used here, for consistency with market_data's
MarketDataProviderPort/MarketDataCachePort, stock_search's
StockSearchProviderPort, and stock_details' StockQuoteProviderPort.

Per PROJECT_CONTEXT.md's Clean Architecture rule, this file may import
from domain/ (entities, exceptions) but must never import FastAPI,
Pydantic, httpx, a database driver, API schemas, a concrete provider, or
anything from the market_data, stock_search, or stock_details modules.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.modules.stock_history.domain.entities import HistoricalSeries
from app.modules.stock_history.domain.exceptions import (  # noqa: F401 -- referenced in docstrings
    HistoryProviderRateLimitedError,
    HistoryProviderTimeoutError,
    HistoryProviderUnavailableError,
    InvalidHistoricalDataError,
)


class HistoricalDataProviderPort(ABC):
    """
    Abstract contract for any backend capable of fetching historical
    OHLCV candle data for a single stock.

    Concrete implementations are responsible for translating their own
    backend's responses and errors into this module's domain exceptions
    (HistoryProviderTimeoutError, HistoryProviderRateLimitedError,
    HistoryProviderUnavailableError, InvalidHistoricalDataError) --
    callers of this port should never need to catch a provider-specific
    exception type.
    """

    @abstractmethod
    async def get_history(
        self,
        display_symbol: str,
        *,
        period: str,
        interval: str,
    ) -> HistoricalSeries:
        """
        Fetch historical candle data for the stock identified by
        ``display_symbol`` over ``period`` at ``interval`` granularity.

        Args:
            display_symbol:
                The UI-facing presentation identifier, such as
                ``"RELIANCE.NSE"``. The application layer is responsible
                for normalizing and validating this value before calling
                the provider.

            period:
                The overall lookback period to fetch, such as ``"1mo"``,
                ``"1y"``, or ``"max"``. This value is already normalized
                and validated by application/services.py.

            interval:
                The candle granularity to fetch, such as ``"1d"``,
                ``"1h"``, or ``"1m"``. This value is already normalized
                and validated by application/services.py.

        Returns:
            Exactly one HistoricalSeries for the requested stock.

            The returned series must preserve the requested ``period`` and
            ``interval`` in its own fields.

            Candle ordering must be preserved exactly as supplied by the
            provider. Implementations must not sort or deduplicate the
            returned data.

            Every candle must otherwise satisfy the stock_history domain
            entity requirements. If the provider response cannot be
            converted safely into valid domain entities, the
            implementation must raise InvalidHistoricalDataError.

        Raises:
            HistoryProviderTimeoutError:
                If the backend does not respond within the configured
                timeout.

            HistoryProviderRateLimitedError:
                If the backend reports that its rate limit has been
                exceeded.

            HistoryProviderUnavailableError:
                If the backend cannot be reached or reports an outage.

            InvalidHistoricalDataError:
                If the backend responds but its data cannot be safely
                converted into a HistoricalSeries.
        """
        raise NotImplementedError