"""
API-layer response schemas for the market_data module's live index
tracking capability.

These Pydantic models define the exact JSON shape returned by
GET /api/v1/market/indices and are the only place in this module that
converts domain entities (IndexQuote, MarketIndicesSnapshot) into a
wire-format response -- domain entities themselves have no knowledge of
JSON, Pydantic, or field naming conventions, per PROJECT_CONTEXT.md's
Clean Architecture rule.

Naming convention note: this endpoint's response fields use camelCase
aliases (displayName, changePercent, asOf, lastUpdated, bankNifty,
indiaVix) per explicit Sprint 3 direction. This is a deliberate,
documented deviation from API_SPEC.md Section 9's snake_case JSON field
convention for this endpoint specifically -- API_SPEC.md should be updated
to record this exception (or this endpoint reconciled to snake_case later)
rather than letting the two documents silently disagree.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_serializer

from app.modules.market_data.domain.entities import (
    IndexQuote,
    IndexSymbol,
    MarketIndicesSnapshot,
)


class IndexQuoteResponse(BaseModel):
    """
    Wire-format representation of a single index's quote.

    `price`, `change`, and `change_percent` are declared as Decimal (never
    float) to preserve the precision carried by the domain entity, and are
    explicitly serialized to strings for JSON output only (see
    `serialize_decimal_field` below) so the JSON response never emits a
    native JSON number for a financial value, consistent with
    API_SPEC.md Section 5's rule that monetary/price values are returned
    as strings. `as_of` is typed AwareDatetime so a naive timestamp is
    rejected at this API boundary rather than silently accepted.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        serialize_by_alias=True,
    )

    display_name: str = Field(alias="displayName")
    price: Decimal
    change: Decimal
    change_percent: Decimal = Field(alias="changePercent")
    as_of: AwareDatetime = Field(alias="asOf")

    @field_serializer(
        "price",
        "change",
        "change_percent",
        when_used="json",
    )
    def serialize_decimal_field(self, value: Decimal) -> str:
        """
        Serializes a Decimal field to its exact string representation when
        producing JSON output, rather than letting Pydantic emit a native
        JSON number -- this is what preserves precision across the API
        boundary and matches API_SPEC.md's convention for financial
        values. Restricted to JSON serialization (`when_used="json"`) so
        Python-mode serialization (e.g. `.model_dump()`) still yields
        actual Decimal instances for in-process use.
        """
        return str(value)

    @classmethod
    def from_domain(cls, quote: IndexQuote) -> "IndexQuoteResponse":
        """
        Builds a response schema instance from a domain IndexQuote entity.

        This is the only place a domain IndexQuote is converted into a
        wire-format object -- the domain entity itself remains unaware
        that this conversion exists.
        """
        return cls(
            display_name=quote.display_name,
            price=quote.price,
            change=quote.change,
            change_percent=quote.change_percent,
            as_of=quote.as_of,
        )


class MarketIndicesResponse(BaseModel):
    """
    Wire-format response for GET /api/v1/market/indices.

    Each tracked index is an optional field because a MarketIndicesSnapshot
    may contain partial data (per the provider port's contract, a
    temporarily unavailable symbol is simply absent from the snapshot
    rather than causing the whole request to fail) -- a missing field here
    means "unavailable right now," not "this index doesn't exist."
    `last_updated` is always required and typed AwareDatetime, since a
    snapshot cannot exist without a timezone-aware `generated_at`
    timestamp (enforced by the domain entity itself).
    """

    model_config = ConfigDict(
        populate_by_name=True,
        serialize_by_alias=True,
    )

    nifty50: IndexQuoteResponse | None = Field(default=None, alias="nifty50")
    sensex: IndexQuoteResponse | None = Field(default=None, alias="sensex")
    bank_nifty: IndexQuoteResponse | None = Field(default=None, alias="bankNifty")
    india_vix: IndexQuoteResponse | None = Field(default=None, alias="indiaVix")
    last_updated: AwareDatetime = Field(alias="lastUpdated")

    @classmethod
    def from_domain(cls, snapshot: MarketIndicesSnapshot) -> "MarketIndicesResponse":
        """
        Builds a response schema instance from a domain
        MarketIndicesSnapshot entity, mapping each IndexSymbol to its
        corresponding named response field.

        This is the only place in the codebase that translates the
        domain's IndexSymbol enum into this endpoint's specific field
        names -- if a new tracked index is added to IndexSymbol later,
        this method (and the corresponding new field above) is where that
        gets surfaced in the API response.
        """
        return cls(
            nifty50=cls._response_for(snapshot, IndexSymbol.NIFTY_50),
            sensex=cls._response_for(snapshot, IndexSymbol.SENSEX),
            bank_nifty=cls._response_for(snapshot, IndexSymbol.BANK_NIFTY),
            india_vix=cls._response_for(snapshot, IndexSymbol.INDIA_VIX),
            last_updated=snapshot.generated_at,
        )

    @staticmethod
    def _response_for(
        snapshot: MarketIndicesSnapshot, symbol: IndexSymbol
    ) -> IndexQuoteResponse | None:
        """
        Looks up `symbol` in `snapshot` and converts it to a response
        object, or returns None if that symbol's quote is absent from the
        snapshot.
        """
        quote = snapshot.get(symbol)
        if quote is None:
            return None
        return IndexQuoteResponse.from_domain(quote)