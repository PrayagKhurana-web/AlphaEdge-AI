"""
API-layer response schemas for the stock_details module.

This Pydantic model defines the exact JSON shape returned by the stock
details (quote) endpoint and is the only place in this module that
converts the domain entity (StockQuote) into a wire-format response --
the domain entity itself has no knowledge of JSON, Pydantic, or field
naming conventions, per PROJECT_CONTEXT.md's Clean Architecture rule.

Naming convention note: like market_data/api/schemas.py and
stock_search/api/schemas.py, this endpoint's response fields use camelCase
aliases (displaySymbol, companyName, changePercent, previousClose, asOf,
etc.) as the same scoped, deliberate deviation from API_SPEC.md Section
9's snake_case JSON field convention already applied to those two
modules. This is now the third module using this exact deviation --
API_SPEC.md should be updated to formally document camelCase as the
convention for these endpoint families rather than continuing to note it
as a one-off exception per file.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_serializer

from app.modules.stock_details.domain.entities import StockQuote
from app.modules.stock_search.domain.entities import StockExchange


class StockQuoteResponse(BaseModel):
    """
    Wire-format representation of a single stock's current quote.

    Mirrors StockQuote field-for-field: no value is recalculated,
    reformatted, rounded, reordered, or defaulted here -- this model is a
    pure wire-format mirror of the domain entity. `price`, `change`,
    `change_percent`, `open_price`, `high_price`, `low_price`, and
    `previous_close` are declared as Decimal (never float) to preserve
    the precision carried by the domain entity, and are explicitly
    serialized to strings for JSON output only (see
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

    symbol: str
    display_symbol: str = Field(alias="displaySymbol")
    company_name: str = Field(alias="companyName")
    exchange: StockExchange
    price: Decimal
    change: Decimal
    change_percent: Decimal = Field(alias="changePercent")
    open_price: Decimal = Field(alias="open")
    high_price: Decimal = Field(alias="high")
    low_price: Decimal = Field(alias="low")
    previous_close: Decimal = Field(alias="previousClose")
    as_of: AwareDatetime = Field(alias="asOf")

    @field_serializer(
        "price",
        "change",
        "change_percent",
        "open_price",
        "high_price",
        "low_price",
        "previous_close",
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
    def from_domain(cls, quote: StockQuote) -> "StockQuoteResponse":
        """
        Builds a response schema instance from a domain StockQuote entity.

        This is the only place a domain StockQuote is converted into a
        wire-format object -- the domain entity itself remains unaware
        that this conversion exists. Every field is copied directly with
        no recalculation, formatting, rounding, reordering, or defaulting.
        """
        return cls(
            symbol=quote.symbol,
            display_symbol=quote.display_symbol,
            company_name=quote.company_name,
            exchange=quote.exchange,
            price=quote.price,
            change=quote.change,
            change_percent=quote.change_percent,
            open_price=quote.open_price,
            high_price=quote.high_price,
            low_price=quote.low_price,
            previous_close=quote.previous_close,
            as_of=quote.as_of,
        )