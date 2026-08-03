"""Domain exceptions for the financial_health module."""

from __future__ import annotations


class FinancialHealthError(Exception):
    """Base exception for financial-health failures."""


class InvalidFinancialHealthRequestError(FinancialHealthError):
    """Raised when the financial-health request is invalid."""


class InsufficientFinancialHealthDataError(FinancialHealthError):
    """Raised when there is not enough usable statement data."""


class InvalidFinancialHealthDataError(FinancialHealthError):
    """Raised when supplied financial data is structurally unusable."""


class FinancialHealthCalculationError(FinancialHealthError):
    """Raised when deterministic scoring fails."""
