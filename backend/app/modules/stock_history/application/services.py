"""
Application-layer use case for fetching historical stock candle data.

This module contains the orchestration logic that validates and
normalizes a caller-supplied display symbol, period, and interval, checks
their mutual compatibility, and delegates to the injected
HistoricalDataProviderPort -- per PROJECT_CONTEXT.md's Clean Architecture
rule, it depends only on application/ports.py and domain/entities.py +
domain/exceptions.py, never on FastAPI, Pydantic, httpx, a database
driver, or any concrete provider implementation.

This layer owns all request validation for this module: display-symbol
format, supported periods, supported intervals, and period/interval
compatibility are all checked here, before a provider is ever contacted.
Provider adapters therefore only ever receive an already-validated,
compatible (display_symbol, period, interval) combination and are not
required to re-validate any of it. Compatibility is checked here rather
than left to the provider so that an unsupported combination fails fast,
with a clear domain-level reason, instead of being silently sent to Yahoo
Finance (or a future provider) and failing there in a way that would have
to be reverse-engineered from a provider-specific error.
"""

from __future__ import annotations

import re

from app.modules.stock_history.application.ports import HistoricalDataProviderPort
from app.modules.stock_history.domain.entities import HistoricalSeries
from app.modules.stock_history.domain.exceptions import InvalidHistoryRequestError

# Supported display symbol format: "<SYMBOL>.<EXCHANGE>", exactly one dot,
# a non-empty symbol with no internal whitespace, and an exchange that is
# exactly "NSE" or "BSE" -- the same convention already validated by
# stock_details.application.services.StockQuoteService.
_DISPLAY_SYMBOL_PATTERN = re.compile(r"^(?P<symbol>\S+)\.(?P<exchange>NSE|BSE)$")

# The complete, exact set of periods this module supports. A frozenset is
# used (rather than a list or a runtime-computed set) so this constant is
# immutable and its membership check is O(1).
_SUPPORTED_PERIODS: frozenset[str] = frozenset(
    {
        "1d",
        "5d",
        "1mo",
        "3mo",
        "6mo",
        "1y",
        "2y",
        "5y",
        "10y",
        "ytd",
        "max",
    }
)

# The complete, exact set of intervals this module supports.
_SUPPORTED_INTERVALS: frozenset[str] = frozenset(
    {
        "1m",
        "2m",
        "5m",
        "15m",
        "30m",
        "60m",
        "90m",
        "1h",
        "1d",
        "5d",
        "1wk",
        "1mo",
        "3mo",
    }
)

# Intervals allowed for any supported period -- daily-and-coarser
# intervals don't accumulate the data volume that makes fine-grained
# intraday intervals impractical over long lookback periods.
_INTERVALS_ALLOWED_FOR_ANY_PERIOD: frozenset[str] = frozenset(
    {"1d", "5d", "1wk", "1mo", "3mo"}
)

# The only periods "1m" may be combined with.
_PERIODS_ALLOWED_FOR_ONE_MINUTE_INTERVAL: frozenset[str] = frozenset(
    {"1d", "5d", "1mo"}
)

# Intervals that require a "medium" granularity restriction: allowed only
# for the periods listed in _PERIODS_ALLOWED_FOR_MEDIUM_INTRADAY_INTERVALS.
_MEDIUM_INTRADAY_INTERVALS: frozenset[str] = frozenset(
    {"2m", "5m", "15m", "30m", "60m", "90m", "1h"}
)
_PERIODS_ALLOWED_FOR_MEDIUM_INTRADAY_INTERVALS: frozenset[str] = frozenset(
    {"1d", "5d", "1mo", "3mo", "6mo", "1y", "2y"}
)


class HistoricalDataService:
    """
    Use case: validate and normalize a caller-supplied display symbol,
    period, and interval, verify their mutual compatibility, and return
    the resulting HistoricalSeries via the injected
    HistoricalDataProviderPort.

    This service is the only place in the module that decides what counts
    as a valid request -- the provider implementation is only ever asked
    to fetch history for an already-validated, compatible combination of
    inputs, and is never expected to perform this validation itself.
    """

    def __init__(self, provider: HistoricalDataProviderPort) -> None:
        """
        Args:
            provider: Historical data backend, satisfying
                HistoricalDataProviderPort.
        """
        self._provider = provider

    async def get_history(
        self,
        display_symbol: str,
        *,
        period: str,
        interval: str,
    ) -> HistoricalSeries:
        """
        Validates `display_symbol`, `period`, and `interval`, and returns
        the resulting HistoricalSeries, fetched via the injected provider.

        Args:
            display_symbol: Raw, caller-supplied display symbol in the
                form "SYMBOL.EXCHANGE" (e.g. "RELIANCE.NSE").
            period: Raw, caller-supplied lookback period (e.g. "1y").
            interval: Raw, caller-supplied candle interval (e.g. "1d").

        Returns:
            The HistoricalSeries returned by the provider, unchanged --
            this method does not sort, modify, or recalculate any part of
            the result.

        Raises:
            InvalidHistoryRequestError: if `display_symbol` is empty
                (after stripping) or does not match the supported
                "SYMBOL.EXCHANGE" format; if `period` is not one of the
                supported periods; if `interval` is not one of the
                supported intervals; or if the requested period and
                interval are not a compatible combination.
            HistoryProviderTimeoutError, HistoryProviderRateLimitedError,
            HistoryProviderUnavailableError, InvalidHistoricalDataError:
                propagated unchanged from the provider.
        """
        normalized_display_symbol, normalized_period, normalized_interval = (
            self._normalize_inputs(display_symbol, period, interval)
        )

        self._validate_display_symbol(normalized_display_symbol)
        self._validate_period(normalized_display_symbol, normalized_period)
        self._validate_interval(normalized_display_symbol, normalized_interval)
        self._validate_period_interval_compatibility(
            normalized_display_symbol, normalized_period, normalized_interval
        )

        return await self._provider.get_history(
            normalized_display_symbol,
            period=normalized_period,
            interval=normalized_interval,
        )

    def _normalize_inputs(
        self, display_symbol: str, period: str, interval: str
    ) -> tuple[str, str, str]:
        """
        Strips leading/trailing whitespace from `display_symbol`,
        `period`, and `interval`.

        Case is preserved exactly as supplied for all three -- this
        module's supported period/interval tokens (e.g. "1mo", "1d") are
        already lowercase by convention, and automatically case-folding
        caller input would mask a genuinely malformed request (e.g.
        "1MO") rather than rejecting it.
        """
        return display_symbol.strip(), period.strip(), interval.strip()

    def _validate_display_symbol(self, normalized_display_symbol: str) -> None:
        """
        Validates that `normalized_display_symbol` is non-empty and
        matches the supported "SYMBOL.EXCHANGE" format.

        Raises:
            InvalidHistoryRequestError: if the display symbol is empty, if
                it does not contain exactly one dot, if the symbol portion
                is empty or contains whitespace, or if the exchange
                portion is not exactly "NSE" or "BSE".
        """
        if not normalized_display_symbol:
            raise InvalidHistoryRequestError(
                normalized_display_symbol,
                reason="display symbol must not be empty",
            )

        if normalized_display_symbol.count(".") != 1:
            raise InvalidHistoryRequestError(
                normalized_display_symbol,
                reason="display symbol must contain exactly one dot in the form SYMBOL.EXCHANGE",
            )

        match = _DISPLAY_SYMBOL_PATTERN.match(normalized_display_symbol)
        if match is None:
            raise InvalidHistoryRequestError(
                normalized_display_symbol,
                reason=(
                    "display symbol must be in the form SYMBOL.EXCHANGE, "
                    "with a non-empty symbol containing no whitespace and "
                    "an exchange of either NSE or BSE"
                ),
            )

    def _validate_period(
        self, normalized_display_symbol: str, normalized_period: str
    ) -> None:
        """
        Validates that `normalized_period` is one of this module's exactly
        supported periods.

        Raises:
            InvalidHistoryRequestError: if `normalized_period` is not a
                member of _SUPPORTED_PERIODS.
        """
        if normalized_period not in _SUPPORTED_PERIODS:
            raise InvalidHistoryRequestError(
                normalized_display_symbol,
                reason=(
                    f"period {normalized_period!r} is not supported; "
                    f"supported periods are: {sorted(_SUPPORTED_PERIODS)}"
                ),
            )

    def _validate_interval(
        self, normalized_display_symbol: str, normalized_interval: str
    ) -> None:
        """
        Validates that `normalized_interval` is one of this module's
        exactly supported intervals.

        Raises:
            InvalidHistoryRequestError: if `normalized_interval` is not a
                member of _SUPPORTED_INTERVALS.
        """
        if normalized_interval not in _SUPPORTED_INTERVALS:
            raise InvalidHistoryRequestError(
                normalized_display_symbol,
                reason=(
                    f"interval {normalized_interval!r} is not supported; "
                    f"supported intervals are: {sorted(_SUPPORTED_INTERVALS)}"
                ),
            )

    def _validate_period_interval_compatibility(
        self,
        normalized_display_symbol: str,
        normalized_period: str,
        normalized_interval: str,
    ) -> None:
        """
        Validates that `normalized_period` and `normalized_interval` are a
        compatible combination, per this module's fixed compatibility
        rules:

          - "1m" is allowed only with period "1d", "5d", or "1mo".
          - "2m", "5m", "15m", "30m", "60m", "90m", and "1h" are allowed
            only with period "1d", "5d", "1mo", "3mo", "6mo", "1y", or
            "2y".
          - "1d", "5d", "1wk", "1mo", and "3mo" are allowed with any
            supported period.

        This check runs after `normalized_period` and `normalized_interval`
        have each already been individually validated, so both are
        guaranteed to be members of their respective supported sets by
        the time this method is called.

        This compatibility is enforced here, in the application layer,
        rather than left to the provider: a request that violates these
        rules is rejected immediately with a clear domain-level reason,
        instead of being sent to the provider and failing there in a way
        that would surface as an opaque provider error unrelated to the
        actual, avoidable problem with the request itself.

        Raises:
            InvalidHistoryRequestError: if `normalized_interval` is "1m"
                and `normalized_period` is not one of "1d", "5d", "1mo";
                or if `normalized_interval` is one of the medium intraday
                intervals and `normalized_period` is not one of the
                periods allowed for that group. Intervals in
                _INTERVALS_ALLOWED_FOR_ANY_PERIOD are never rejected here.
        """
        if normalized_interval in _INTERVALS_ALLOWED_FOR_ANY_PERIOD:
            return

        if normalized_interval == "1m":
            if normalized_period not in _PERIODS_ALLOWED_FOR_ONE_MINUTE_INTERVAL:
                raise InvalidHistoryRequestError(
                    normalized_display_symbol,
                    reason=(
                        "interval '1m' is only supported with period "
                        f"{sorted(_PERIODS_ALLOWED_FOR_ONE_MINUTE_INTERVAL)}, "
                        f"got period {normalized_period!r}"
                    ),
                )
            return

        if normalized_interval in _MEDIUM_INTRADAY_INTERVALS:
            if normalized_period not in _PERIODS_ALLOWED_FOR_MEDIUM_INTRADAY_INTERVALS:
                raise InvalidHistoryRequestError(
                    normalized_display_symbol,
                    reason=(
                        f"interval {normalized_interval!r} is only "
                        "supported with period "
                        f"{sorted(_PERIODS_ALLOWED_FOR_MEDIUM_INTRADAY_INTERVALS)}, "
                        f"got period {normalized_period!r}"
                    ),
                )
            return