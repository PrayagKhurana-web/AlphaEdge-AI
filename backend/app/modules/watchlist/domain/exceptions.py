class WatchlistError(Exception):
    """Base exception for watchlist operations."""


class WatchlistItemAlreadyExistsError(WatchlistError):
    """Raised when a stock is already saved in the watchlist."""


class WatchlistItemNotFoundError(WatchlistError):
    """Raised when a requested watchlist item does not exist."""
