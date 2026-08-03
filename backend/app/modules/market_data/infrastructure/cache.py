"""
In-memory implementation of MarketDataCachePort, intended for local
development and testing.

This adapter stores a single MarketIndicesSnapshot in process memory with
TTL-based expiry. It has no external dependencies (no Redis, no
serialization format) -- a Redis-backed implementation satisfying the same
MarketDataCachePort interface can be introduced later for production use
without any change to application/services.py or the API layer, per
PROJECT_CONTEXT.md's Clean Architecture rule that infrastructure adapters
are swappable behind application-layer ports.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

from app.modules.market_data.application.ports import MarketDataCachePort
from app.modules.market_data.domain.entities import MarketIndicesSnapshot


@dataclass(frozen=True, slots=True)
class _CacheEntry:
    """
    Internal storage record pairing a cached snapshot with its expiry.

    Attributes:
        snapshot: The cached MarketIndicesSnapshot, stored and returned
            as-is -- this adapter never mutates or copies it, since
            MarketIndicesSnapshot is itself an immutable domain entity
            (frozen dataclass with a read-only `quotes` mapping).
        expires_at_monotonic: The time.monotonic() value at which this
            entry should be considered expired. A monotonic clock is used
            instead of wall-clock time so that system clock adjustments
            (NTP sync, manual changes, DST) cannot cause premature or
            delayed expiry.
    """

    snapshot: MarketIndicesSnapshot
    expires_at_monotonic: float


class InMemoryMarketDataCache(MarketDataCachePort):
    """
    Single-process, in-memory MarketDataCachePort implementation with TTL
    expiry, safe for concurrent access from multiple async tasks within
    one process.

    Not suitable for multi-process or multi-instance deployments (each
    process would have its own independent cache) -- appropriate for local
    development and single-instance environments only. A shared backend
    (e.g. Redis) is required once the application runs as more than one
    process, and would be introduced as a separate class implementing the
    same MarketDataCachePort interface.
    """

    def __init__(self) -> None:
        self._entry: _CacheEntry | None = None
        # A single asyncio.Lock guards all read/write access to `_entry`.
        # asyncio.Lock (not a threading.Lock) is correct here because this
        # class is only ever accessed from coroutines running on the same
        # event loop -- a threading lock would be the wrong primitive
        # (and could deadlock or block the event loop) in that context.
        self._lock = asyncio.Lock()

    async def get_market_indices_snapshot(self) -> MarketIndicesSnapshot | None:
        """
        Returns the cached snapshot if present and not yet expired,
        otherwise None.

        Holds the lock for the full check-and-read so a concurrent
        `set_market_indices_snapshot()` call cannot interleave between
        reading `_entry` and evaluating its expiry.
        """
        async with self._lock:
            entry = self._entry
            if entry is None:
                return None
            if time.monotonic() >= entry.expires_at_monotonic:
                self._entry = None
                return None
            return entry.snapshot

    async def set_market_indices_snapshot(
        self,
        snapshot: MarketIndicesSnapshot,
        *,
        ttl_seconds: int,
    ) -> None:
        """
        Stores `snapshot` as the current cached snapshot, expiring after
        `ttl_seconds` seconds from the moment the entry is actually
        written (not from when this method was called), so time spent
        waiting for the lock is never counted against the TTL.

        `ttl_seconds` is validated before attempting to acquire the lock,
        so an invalid call fails immediately without contending for the
        lock at all. The expiry calculation and the entry write itself
        both happen only after the lock is held, so a concurrent
        `get_market_indices_snapshot()` call cannot observe a
        partially-updated state, and the TTL window starts at the actual
        moment of storage.

        Args:
            snapshot: The snapshot to cache. Stored directly (not copied)
                since it is an immutable domain entity.
            ttl_seconds: Number of seconds until this entry expires. Must
                be strictly positive.

        Raises:
            ValueError: if `ttl_seconds` is less than or equal to zero.
        """
        if ttl_seconds <= 0:
            raise ValueError(
                f"ttl_seconds must be strictly positive, got {ttl_seconds!r}"
            )

        async with self._lock:
            expires_at_monotonic = time.monotonic() + ttl_seconds
            self._entry = _CacheEntry(
                snapshot=snapshot,
                expires_at_monotonic=expires_at_monotonic,
            )