"""Application service for the quant_engine module.

Orchestrates the first deterministic technical-analysis snapshot use
case by coordinating two independently swappable dependencies: a
``HistoricalDataProviderPort`` (candle retrieval) and a
``TechnicalAnalysisCalculatorPort`` (indicator calculation). This
service performs orchestration only -- it never calculates an
indicator, modifies a calculated value, or reconstructs the snapshot
itself. It is unaware of FastAPI, HTTP status codes, Pydantic, JSON,
httpx, Yahoo Finance, pandas, NumPy, TA-Lib, database models, and
caching.

This service produces a deterministic, rule-based technical-analysis
snapshot only. It does not predict future prices, estimate probabilities,
or generate financial advice.
"""

from datetime import datetime, timezone

from ..domain.entities import TechnicalAnalysisSnapshot
from ..domain.exceptions import InvalidTechnicalAnalysisRequestError
from .ports import HistoricalDataProviderPort, TechnicalAnalysisCalculatorPort


class QuantEngineService:
    """Orchestrates a deterministic technical-analysis snapshot.

    Coordinates a ``HistoricalDataProviderPort`` and a
    ``TechnicalAnalysisCalculatorPort`` without performing any
    calculation itself.
    """

    def __init__(
        self,
        historical_data_provider: HistoricalDataProviderPort,
        technical_analysis_calculator: TechnicalAnalysisCalculatorPort,
    ) -> None:
        self._historical_data_provider = historical_data_provider
        self._technical_analysis_calculator = technical_analysis_calculator

    async def get_technical_analysis(
        self,
        display_symbol: str,
        *,
        interval: str = "1d",
        period: str = "1y",
        currency: str | None = None,
    ) -> TechnicalAnalysisSnapshot:
        """Retrieve historical data and calculate a technical-analysis snapshot.

        Validates only that ``display_symbol`` is a non-empty string,
        trimming surrounding whitespace -- the same minimal,
        provider-agnostic check owned at this layer by stock_history's
        own application service. No format enforcement, case
        normalization, or Yahoo-specific/provider-specific symbol
        conversion happens here; that belongs to whichever adapter
        implements ``HistoricalDataProviderPort``. ``interval`` and
        ``period`` are passed through unvalidated at this layer,
        matching the same historical candle request shape stock_history's
        application service accepts.

        ``currency`` is used exactly as supplied by the caller and is
        never guessed or fabricated (e.g. as "INR" or "USD" based on
        exchange) -- if the caller does not have a currency to supply,
        it remains ``None``.

        ``calculated_at`` is derived from the system clock
        (``datetime.now(timezone.utc)``); no dedicated clock abstraction
        exists elsewhere in the project for this first implementation.

        Domain exceptions raised by either dependency -- including
        stock_history's own domain exceptions surfaced through
        ``HistoricalDataProviderPort``, and quant_engine's own
        ``InsufficientHistoricalDataError``, ``InvalidHistoricalDataError``,
        or ``TechnicalCalculationError`` raised by the calculator -- are
        not caught or translated here; they propagate unchanged, matching
        the convention already established by company_fundamentals'
        application service.

        Raises:
            InvalidTechnicalAnalysisRequestError: if `display_symbol` is
                not a non-empty string.
        """
        normalized_display_symbol = QuantEngineService._validate_display_symbol(
            display_symbol
        )

        historical_series = await self._historical_data_provider.get_history(
            normalized_display_symbol,
            interval=interval,
            period=period,
        )

        calculated_at = datetime.now(timezone.utc)

        return self._technical_analysis_calculator.calculate_snapshot(
            historical_series,
            calculated_at=calculated_at,
            currency=currency,
        )

    @staticmethod
    def _validate_display_symbol(display_symbol: str) -> str:
        """Validate and trim the public display symbol.

        Provider-specific symbol formatting and conversion are handled by
        the historical-data adapter.

        Raises:
            InvalidTechnicalAnalysisRequestError: if `display_symbol` is not
                a non-empty string.
        """
        if not isinstance(display_symbol, str) or not display_symbol.strip():
            raise InvalidTechnicalAnalysisRequestError(
                "display_symbol must be a non-empty string."
            )

        return display_symbol.strip()