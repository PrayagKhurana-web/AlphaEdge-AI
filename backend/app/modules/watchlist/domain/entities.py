from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class WatchlistItem:
    """Stock saved in a user's watchlist."""

    id: int
    user_id: int
    display_symbol: str
    exchange: str
    created_at: datetime
