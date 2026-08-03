"""Domain entities for the company_fundamentals module.

Defines the framework-agnostic representation of a company's core
fundamentals data. This entity is a plain, immutable snapshot: it has no
awareness of JSON, Pydantic, FastAPI, HTTP, Yahoo Finance, serialization
aliases, or frontend formatting concerns such as crores, lakhs, millions,
or billions. Normalizing raw provider data into this shape is the
responsibility of the infrastructure layer; the application layer passes
it through unchanged.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from ...stock_search.domain.entities import StockExchange


@dataclass(frozen=True, slots=True)
class CompanyFundamentals:
    """A point-in-time snapshot of a company's core fundamentals.

    Any field the provider does not supply is represented as ``None``
    rather than omitted, zeroed, or estimated. All numeric fields use
    ``Decimal`` and remain exactly as normalized by the infrastructure
    layer — no rounding, scaling, or reformatting is applied here.
    ``fetched_at`` records when this snapshot was retrieved, which is not
    necessarily the same as the provider's underlying financial reporting
    date.
    """

    # Identity
    symbol: str
    display_symbol: str
    company_name: str
    exchange: StockExchange
    sector: str | None
    industry: str | None
    website: str | None
    business_summary: str | None

    # Market and valuation
    market_cap: Decimal | None
    enterprise_value: Decimal | None
    trailing_pe: Decimal | None
    forward_pe: Decimal | None
    price_to_book: Decimal | None
    enterprise_to_revenue: Decimal | None
    enterprise_to_ebitda: Decimal | None

    # Per-share and profitability
    trailing_eps: Decimal | None
    forward_eps: Decimal | None
    book_value_per_share: Decimal | None
    return_on_equity: Decimal | None
    return_on_assets: Decimal | None
    profit_margin: Decimal | None
    operating_margin: Decimal | None

    # Growth
    revenue_growth: Decimal | None
    earnings_growth: Decimal | None

    # Balance-sheet and income highlights
    total_revenue: Decimal | None
    net_income: Decimal | None
    total_cash: Decimal | None
    total_debt: Decimal | None
    debt_to_equity: Decimal | None
    free_cash_flow: Decimal | None
    operating_cash_flow: Decimal | None

    # Dividend
    dividend_rate: Decimal | None
    dividend_yield: Decimal | None
    payout_ratio: Decimal | None

    # Trading reference values
    fifty_two_week_high: Decimal | None
    fifty_two_week_low: Decimal | None
    fifty_day_average: Decimal | None
    two_hundred_day_average: Decimal | None

    # Metadata
    currency: str | None
    fetched_at: datetime