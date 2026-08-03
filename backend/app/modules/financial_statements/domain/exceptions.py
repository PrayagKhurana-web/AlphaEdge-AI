"""Domain exceptions for the financial_statements module."""

from __future__ import annotations


class FinancialStatementsError(Exception):
    """Base exception for financial-statements failures."""


class InvalidFinancialStatementsRequestError(FinancialStatementsError):
    """Raised when the symbol or requested period is invalid."""


class InvalidFinancialStatementsDataError(FinancialStatementsError):
    """Raised when the provider returns no usable statement data."""


class FinancialStatementsProviderUnavailableError(FinancialStatementsError):
    """Raised when the upstream provider is unavailable."""


class FinancialStatementsProviderTimeoutError(FinancialStatementsError):
    """Raised when the upstream provider request times out."""


class FinancialStatementsProviderRateLimitedError(FinancialStatementsError):
    """Raised when the upstream provider rate-limits the request."""

    def __init__(
        self,
        message: str,
        *,
        retry_after_seconds: int | None = None,
    ) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds
