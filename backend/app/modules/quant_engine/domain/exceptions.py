"""Domain exceptions for the quant_engine module.

These exceptions form the error vocabulary for the deterministic
technical-analysis snapshot use case and are raised by the application
and infrastructure layers to signal failure conditions in a
framework-agnostic way. The API layer is responsible for translating
them into appropriate HTTP responses; this module has no awareness of
HTTP, FastAPI, Pydantic, JSON, httpx, pandas, NumPy, Yahoo Finance,
database models, or caching.

This first iteration covers only the errors needed for a deterministic
technical-analysis snapshot -- prediction, model, broker, portfolio, AI
analysis, database, and cache failures are outside this scope and are
intentionally not represented here.
"""


class QuantEngineError(Exception):
    """Base exception for all errors raised by the quant_engine module.

    All other exceptions in this module inherit from this class, allowing
    callers to catch every quant_engine-specific failure with a single
    except clause when finer-grained handling is not required.
    """


class InvalidTechnicalAnalysisRequestError(QuantEngineError):
    """Raised when a technical-analysis request is malformed or unsupported.

    This covers cases such as an empty or malformed display symbol, an
    unsupported candle interval, or otherwise invalid period/candle
    request inputs. It is intentionally general enough for the
    application service to raise without embedding HTTP terminology.
    """


class InsufficientHistoricalDataError(QuantEngineError):
    """Raised when there are not enough usable candles for a reliable snapshot.

    This covers cases where valid historical data exists but does not
    contain enough usable candles to calculate the requested technical
    snapshot reliably (e.g. too few candles for a given lookback
    window).
    """

    def __init__(
        self,
        *args: object,
        available_candle_count: int,
        required_candle_count: int,
    ) -> None:
        super().__init__(*args)
        self._available_candle_count = available_candle_count
        self._required_candle_count = required_candle_count

    @property
    def available_candle_count(self) -> int:
        """The number of usable candles that were actually available."""
        return self._available_candle_count

    @property
    def required_candle_count(self) -> int:
        """The minimum number of candles required for the calculation."""
        return self._required_candle_count


class InvalidHistoricalDataError(QuantEngineError):
    """Raised when the supplied OHLCV series is unusable for calculations.

    This covers cases such as candles not ordered as expected, duplicate
    timestamps, invalid high/low/open/close relationships, missing
    required close values, or non-finite or otherwise unusable numeric
    values. This exception only defines the error type; detecting these
    conditions is the responsibility of the calculation logic that
    raises it.
    """


class TechnicalCalculationError(QuantEngineError):
    """Raised when technical-indicator calculation fails on valid input.

    This represents an internal failure while calculating deterministic
    technical indicators despite structurally valid input, without
    exposing library or implementation details.
    """