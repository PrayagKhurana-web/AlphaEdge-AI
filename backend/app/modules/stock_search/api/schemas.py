"""
API-layer response schemas for the stock_search module.

These Pydantic models define the exact JSON shape returned by the
stock_search endpoints and are the only place in this module that
converts domain entities (StockSearchResult, StockSearchResults) into a
wire-format response -- domain entities themselves have no knowledge of
JSON, Pydantic, or field naming conventions, per PROJECT_CONTEXT.md's
Clean Architecture rule.

Naming convention note: like market_data/api/schemas.py, this endpoint's
response fields use camelCase aliases (companyName, displaySymbol) as a
deliberate, documented deviation from API_SPEC.md Section 9's snake_case
JSON field convention. API_SPEC.md should be updated to record this
exception (or these endpoints reconciled to snake_case later) rather than
letting the two documents silently disagree.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.modules.stock_search.domain.entities import (
    StockExchange,
    StockSearchResult,
    StockSearchResults,
)


class StockSearchResultResponse(BaseModel):
    """
    Wire-format representation of a single stock search match.

    Mirrors StockSearchResult field-for-field: `symbol` is the canonical
    internal identifier, `exchange` identifies which exchange the match
    was found on, and `display_symbol` is the separate, UI-facing
    presentation identifier (per StockSearchResult's own documentation of
    why the two are kept distinct). No field is derived, reordered, or
    filtered here -- this model is a pure wire-format mirror of the domain
    entity.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        serialize_by_alias=True,
    )

    symbol: str
    company_name: str = Field(alias="companyName")
    exchange: StockExchange
    display_symbol: str = Field(alias="displaySymbol")

    @classmethod
    def from_domain(cls, result: StockSearchResult) -> "StockSearchResultResponse":
        """
        Builds a response schema instance from a domain StockSearchResult
        entity.

        This is the only place a domain StockSearchResult is converted
        into a wire-format object -- the domain entity itself remains
        unaware that this conversion exists. No value is transformed,
        reformatted, or defaulted here beyond a direct field-for-field
        copy.
        """
        return cls(
            symbol=result.symbol,
            company_name=result.company_name,
            exchange=result.exchange,
            display_symbol=result.display_symbol,
        )


class StockSearchResponse(BaseModel):
    """
    Wire-format response for the stock search endpoint(s).

    `results` is declared as a list (not the tuple used internally by the
    domain entity StockSearchResults) because this is a wire-format
    response model, not an immutable domain entity -- Pydantic and JSON
    serialization both operate on lists natively, and there is no
    immutability requirement to preserve once the data has crossed into
    the API response layer.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        serialize_by_alias=True,
    )

    results: list[StockSearchResultResponse]

    @classmethod
    def from_domain(cls, results: StockSearchResults) -> "StockSearchResponse":
        """
        Builds a response schema instance from a domain StockSearchResults
        collection.

        Converts each contained StockSearchResult via
        StockSearchResultResponse.from_domain, preserving the exact order
        supplied by the domain entity. This method never sorts,
        deduplicates, or filters -- any such decision belongs to the
        application layer (which already handles limit truncation) or the
        infrastructure provider (which already handles deduplication by
        (exchange, symbol)), not to this API-layer conversion step.
        """
        return cls(
            results=[
                StockSearchResultResponse.from_domain(result)
                for result in results.results
            ]
        )