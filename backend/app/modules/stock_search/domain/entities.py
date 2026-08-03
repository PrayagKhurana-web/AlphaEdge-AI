"""
Domain entities for the stock_search module.

These are pure Python objects with zero framework dependencies (no
FastAPI, no Pydantic, no HTTP client, no infrastructure-layer concern).
They represent the concept of a "stock search result" independent of
where the search was performed or how it's transported. Per
PROJECT_CONTEXT.md's Clean Architecture rule, this file must never import
from application/, infrastructure/, or api/.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum


class StockExchange(str, Enum):
    """
    Canonical identifiers for the exchanges this module can return search
    results from.

    Deliberately small and specific to the Indian exchanges AlphaEdge AI
    targets (per PROJECT_CONTEXT.md's Project Vision). Extending this
    later (e.g. adding a new exchange) is a one-line addition here, not a
    hunt through string literals in application/infrastructure/api code.
    """

    NSE = "NSE"
    BSE = "BSE"


def _require_non_empty(value: str, field_name: str) -> None:
    """
    Raises ValueError if `value` is empty or consists only of whitespace.

    Centralizing this check keeps the validation rule identical across
    every string field below, rather than each dataclass writing its own
    slightly different check.
    """
    if not value or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string, got {value!r}")


@dataclass(frozen=True, slots=True)
class StockSearchResult:
    """
    A single stock matched by a search query.

    Attributes:
        symbol: The canonical trading symbol on `exchange` (e.g.
            "RELIANCE"). This is the raw symbol as tracked internally --
            distinct from `display_symbol`, which is a separate
            presentation-facing identifier (see below).
        company_name: The issuing company's display name (e.g.
            "Reliance Industries Limited").
        exchange: The exchange this result was matched on.
        display_symbol: A UI-facing presentation identifier (e.g.
            "RELIANCE.NSE"), kept deliberately separate from `symbol` so
            presentation conventions (exchange suffixes, formatting
            changes, future localization, etc.) can evolve independently
            of the canonical internal identifier -- a change to how a
            symbol is displayed should never require touching what
            `symbol` means to the rest of the system.

    All string fields are normalized (leading/trailing whitespace
    stripped) before validation, so this entity can never be constructed
    with accidental surrounding whitespace in any of its string
    attributes.

    Raises:
        ValueError: if `symbol`, `company_name`, or `display_symbol` is
            empty or whitespace-only after stripping.
    """

    symbol: str
    company_name: str
    exchange: StockExchange
    display_symbol: str

    def __post_init__(self) -> None:
        # The dataclass is frozen, so normal attribute assignment
        # (self.symbol = ...) is disallowed even inside __post_init__.
        # object.__setattr__ bypasses that restriction for these
        # intentional, controlled normalization writes: each string field
        # is stripped of leading/trailing whitespace before validation, so
        # the stored value -- not just the value checked -- is guaranteed
        # whitespace-normalized.
        object.__setattr__(self, "symbol", self.symbol.strip())
        object.__setattr__(self, "company_name", self.company_name.strip())
        object.__setattr__(self, "display_symbol", self.display_symbol.strip())

        _require_non_empty(self.symbol, "StockSearchResult.symbol")
        _require_non_empty(self.company_name, "StockSearchResult.company_name")
        _require_non_empty(self.display_symbol, "StockSearchResult.display_symbol")


@dataclass(frozen=True, slots=True)
class StockSearchResults:
    """
    An ordered, immutable collection of stock search results for a single
    query.

    Attributes:
        results: An immutable, ordered sequence of StockSearchResult
            entries, in the order they should be presented (typically
            relevance order, as determined by whichever search mechanism
            produced them -- this entity itself has no notion of ranking
            logic). Stored as a tuple rather than a list: a tuple is
            inherently immutable, so unlike MarketIndicesSnapshot's
            mapping (which required a MappingProxyType wrapper to prevent
            write-through), converting any supplied iterable into a tuple
            here is sufficient on its own to guarantee that neither
            `results` itself nor the original iterable's later mutation
            (if it was a list) can alter this entity after construction.

    The order of `results` is significant and preserved exactly as
    supplied; this entity does not re-sort or deduplicate.
    """

    results: tuple[StockSearchResult, ...]

    def __post_init__(self) -> None:
        # The dataclass is frozen, so normal attribute assignment
        # (self.results = ...) is disallowed even inside __post_init__.
        # object.__setattr__ bypasses that restriction for this one,
        # intentional, controlled write. Wrapping the supplied iterable in
        # tuple(...) both defends against a caller passing a mutable list
        # (whose later mutation must not leak into this entity) and
        # normalizes any iterable input into the declared tuple type.
        object.__setattr__(self, "results", tuple(self.results))

    def __len__(self) -> int:
        """Returns the number of results in this collection."""
        return len(self.results)

    def is_empty(self) -> bool:
        """Returns True if this collection contains zero results."""
        return len(self.results) == 0

    @classmethod
    def from_iterable(cls, results: Iterable[StockSearchResult]) -> "StockSearchResults":
        """
        Convenience constructor building a StockSearchResults from any
        iterable of StockSearchResult (e.g. a generator produced while
        assembling results), rather than requiring callers to materialize
        a tuple themselves first.
        """
        return cls(results=tuple(results))