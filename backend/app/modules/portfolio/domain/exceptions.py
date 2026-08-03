from __future__ import annotations


class PortfolioError(Exception):
    """Base exception for portfolio operations."""


class PortfolioHoldingAlreadyExistsError(PortfolioError):
    """Raised when a user already owns a row for the requested stock."""


class PortfolioHoldingNotFoundError(PortfolioError):
    """Raised when the requested holding does not exist."""


class InvalidPortfolioHoldingError(PortfolioError, ValueError):
    """Raised when symbol, quantity or average price is invalid."""
