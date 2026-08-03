"""Domain exceptions for the company_fundamentals module.

These exceptions form the module's error vocabulary and are raised by the
application and infrastructure layers to signal failure conditions in a
framework-agnostic way. The API layer is responsible for translating them
into appropriate HTTP responses; this module has no awareness of HTTP,
FastAPI, or any transport concern.
"""


class CompanyFundamentalsError(Exception):
    """Base exception for all errors raised by the company_fundamentals module.

    All other exceptions in this module inherit from this class, allowing
    callers to catch every company_fundamentals-specific failure with a
    single except clause when finer-grained handling is not required.
    """


class InvalidFundamentalsRequestError(CompanyFundamentalsError):
    """Raised when a fundamentals request is malformed or unresolvable.

    This covers cases such as an unknown or invalid ``display_symbol``
    that cannot be mapped to a fundamentals lookup.
    """


class InvalidFundamentalsDataError(CompanyFundamentalsError):
    """Raised when the provider returns data that cannot be trusted or used.

    This covers malformed, structurally invalid, or otherwise unusable
    fundamentals data returned by the underlying provider.
    """


class FundamentalsProviderUnavailableError(CompanyFundamentalsError):
    """Raised when the fundamentals data provider cannot be reached.

    This covers connection failures, non-2xx provider responses, and
    other conditions indicating the provider is currently unavailable.
    """


class FundamentalsProviderTimeoutError(CompanyFundamentalsError):
    """Raised when a request to the fundamentals data provider times out."""


class FundamentalsProviderRateLimitedError(CompanyFundamentalsError):
    """Raised when the fundamentals data provider rate-limits the request.

    Carries an optional ``retry_after_seconds`` hint, when supplied by the
    provider, indicating how long a caller should wait before retrying.
    """

    def __init__(
        self,
        *args: object,
        retry_after_seconds: int | None = None,
    ) -> None:
        super().__init__(*args)
        self._retry_after_seconds = retry_after_seconds

    @property
    def retry_after_seconds(self) -> int | None:
        """The provider-supplied retry hint, in seconds, if available."""
        return self._retry_after_seconds