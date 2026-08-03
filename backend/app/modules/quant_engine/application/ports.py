"""Application-layer ports for the quant_engine module.

The application layer depends only on these two abstractions, never on
a concrete data source or calculation library. Splitting the
technical-analysis use case into two separate ports keeps data
retrieval and indicator calculation independently swappable and
testable:

- ``HistoricalDataProviderPort`` retrieves historical OHLCV candle data
  only. It performs no calculation.
- ``TechnicalAnalysisCalculatorPort`` calculates deterministic technical
  indicators from already-retrieved candle data only. It performs no
  data fetching.

Neither port performs prediction, probability scoring, or
financial-advice generation -- both are limited to the deterministic
technical-analysis snapshot described by quant_engine's domain layer.

``HistoricalDataProviderPort`` reuses stock_history's own
``HistoricalSeries`` domain entity as its return type rather than
duplicating a candle/series dataclass inside quant_engine. This is a
domain-to-domain reuse across module boundaries (the same pattern
company_fundamentals and stock_history already use for
``StockExchange``), not a dependency on stock_history's application or
infrastructure layers: quant_engine's application layer never imports
stock_history's application service or provider classes, only its
domain entity. Any concrete object satisfying this port's method
signature -- including an adapter wrapping stock_history's own
application service -- structurally satisfies it, since this is a
``Protocol``.
"""

from datetime import datetime
from typing import Protocol

from ..domain.entities import TechnicalAnalysisSnapshot
from ...stock_history.domain.entities import HistoricalSeries


class HistoricalDataProviderPort(Protocol):
    """Abstraction for retrieving historical OHLCV candle data.

    Retrieves data only -- it never calculates indicators, trend, or
    signals.
    """

    async def get_history(
        self,
        display_symbol: str,
        *,
        interval: str,
        period: str,
    ) -> HistoricalSeries:
        """Retrieve a historical candle series for a symbol.

        ``display_symbol`` is the normalized public symbol already
        accepted by the API layer. ``interval`` and ``period`` mirror
        stock_history's own request shape.

        Implementations may raise
        ``InvalidTechnicalAnalysisRequestError`` for a malformed or
        unsupported request, or the relevant existing stock_history
        domain exceptions, leaving translation of those exceptions to
        the application service.
        """
        ...


class TechnicalAnalysisCalculatorPort(Protocol):
    """Abstraction for calculating a deterministic technical-analysis snapshot.

    Calculates indicators from already-retrieved candle data only -- it
    never fetches data itself.
    """

    def calculate_snapshot(
        self,
        historical_series: HistoricalSeries,
        *,
        calculated_at: datetime,
        currency: str | None,
    ) -> TechnicalAnalysisSnapshot:
        """Calculate a technical-analysis snapshot from a candle series.

        ``historical_series`` supplies the identity fields
        (``symbol``, ``display_symbol``, ``interval``) and the OHLCV
        candles the calculation is based on. ``calculated_at`` is the
        timezone-aware moment the snapshot is being produced.
        ``currency`` is passed separately because it is not part of
        ``HistoricalSeries`` but is part of ``TechnicalAnalysisSnapshot``.

        This method performs deterministic, rule-based calculation only
        -- it does not predict future prices or generate financial
        advice.

        Implementations may raise ``InsufficientHistoricalDataError`` if
        ``historical_series`` does not contain enough usable candles for
        a reliable calculation, ``InvalidHistoricalDataError`` if the
        supplied series is malformed, inconsistent, or otherwise unusable
        for calculation, or ``TechnicalCalculationError`` if calculation
        fails despite structurally valid input.
        """
        ...