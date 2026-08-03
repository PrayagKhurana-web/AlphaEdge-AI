"""API response schemas for the company_fundamentals module.

This module defines the JSON response shape returned by the company
fundamentals endpoint and provides the conversion logic from the domain
entity (``CompanyFundamentals``) into that shape.

The domain entity remains completely unaware of JSON or Pydantic — it is
a plain, framework-agnostic dataclass. All serialization concerns
(camelCase aliases, string-encoded Decimal values, timezone-aware
timestamps) live here, at the API boundary, following the same scoped
camelCase convention used by the ``market_data``, ``stock_search``,
``stock_details``, and ``stock_history`` API schemas.

Key serialization behaviors:

- Every monetary, ratio, percentage, per-share, growth, cash-flow,
  dividend, and trading-reference field is optional and serialized as an
  exact string in JSON mode to avoid floating-point precision loss. In
  Python mode (``model_dump()``), the underlying ``Decimal`` instances
  are preserved unchanged.
- Missing optional values remain ``null`` — they are never substituted
  with ``""``, ``0``, or ``"N/A"``.
- Percentages and ratios are passed through exactly as supplied by the
  domain entity; no scaling, rounding, or reformatting occurs here.
- ``fetchedAt`` is timezone-aware and represents retrieval time, not
  necessarily the provider's financial reporting date.
"""

from decimal import Decimal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_serializer

from ..domain.entities import CompanyFundamentals
from ...stock_search.domain.entities import StockExchange


class CompanyFundamentalsResponse(BaseModel):
    """A company's core fundamentals snapshot in the API response shape.

    Internal field names use snake_case; JSON output uses the scoped
    camelCase aliases (e.g. ``display_symbol`` -> ``displaySymbol``,
    ``two_hundred_day_average`` -> ``twoHundredDayAverage``). Every
    Decimal field is optional and is serialized as an exact string in
    JSON mode to preserve precision; Python-mode ``model_dump()`` keeps
    the original ``Decimal`` instances.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        serialize_by_alias=True,
    )

    # Identity
    symbol: str
    display_symbol: str = Field(alias="displaySymbol")
    company_name: str = Field(alias="companyName")
    exchange: StockExchange
    sector: str | None
    industry: str | None
    website: str | None
    business_summary: str | None = Field(alias="businessSummary")

    # Market and valuation
    market_cap: Decimal | None = Field(alias="marketCap")
    enterprise_value: Decimal | None = Field(alias="enterpriseValue")
    trailing_pe: Decimal | None = Field(alias="trailingPE")
    forward_pe: Decimal | None = Field(alias="forwardPE")
    price_to_book: Decimal | None = Field(alias="priceToBook")
    enterprise_to_revenue: Decimal | None = Field(alias="enterpriseToRevenue")
    enterprise_to_ebitda: Decimal | None = Field(alias="enterpriseToEbitda")

    # Per-share and profitability
    trailing_eps: Decimal | None = Field(alias="trailingEps")
    forward_eps: Decimal | None = Field(alias="forwardEps")
    book_value_per_share: Decimal | None = Field(alias="bookValuePerShare")
    return_on_equity: Decimal | None = Field(alias="returnOnEquity")
    return_on_assets: Decimal | None = Field(alias="returnOnAssets")
    profit_margin: Decimal | None = Field(alias="profitMargin")
    operating_margin: Decimal | None = Field(alias="operatingMargin")

    # Growth
    revenue_growth: Decimal | None = Field(alias="revenueGrowth")
    earnings_growth: Decimal | None = Field(alias="earningsGrowth")

    # Balance-sheet and income highlights
    total_revenue: Decimal | None = Field(alias="totalRevenue")
    net_income: Decimal | None = Field(alias="netIncome")
    total_cash: Decimal | None = Field(alias="totalCash")
    total_debt: Decimal | None = Field(alias="totalDebt")
    debt_to_equity: Decimal | None = Field(alias="debtToEquity")
    free_cash_flow: Decimal | None = Field(alias="freeCashFlow")
    operating_cash_flow: Decimal | None = Field(alias="operatingCashFlow")

    # Dividend
    dividend_rate: Decimal | None = Field(alias="dividendRate")
    dividend_yield: Decimal | None = Field(alias="dividendYield")
    payout_ratio: Decimal | None = Field(alias="payoutRatio")

    # Trading reference values
    fifty_two_week_high: Decimal | None = Field(alias="fiftyTwoWeekHigh")
    fifty_two_week_low: Decimal | None = Field(alias="fiftyTwoWeekLow")
    fifty_day_average: Decimal | None = Field(alias="fiftyDayAverage")
    two_hundred_day_average: Decimal | None = Field(alias="twoHundredDayAverage")

    # Metadata
    currency: str | None
    fetched_at: AwareDatetime = Field(alias="fetchedAt")

    @field_serializer(
        "market_cap",
        "enterprise_value",
        "trailing_pe",
        "forward_pe",
        "price_to_book",
        "enterprise_to_revenue",
        "enterprise_to_ebitda",
        "trailing_eps",
        "forward_eps",
        "book_value_per_share",
        "return_on_equity",
        "return_on_assets",
        "profit_margin",
        "operating_margin",
        "revenue_growth",
        "earnings_growth",
        "total_revenue",
        "net_income",
        "total_cash",
        "total_debt",
        "debt_to_equity",
        "free_cash_flow",
        "operating_cash_flow",
        "dividend_rate",
        "dividend_yield",
        "payout_ratio",
        "fifty_two_week_high",
        "fifty_two_week_low",
        "fifty_day_average",
        "two_hundred_day_average",
        when_used="json",
    )
    def serialize_decimal_fields(self, value: Decimal | None) -> str | None:
        """Serialize optional Decimal fields as exact strings in JSON mode.

        Returns ``None`` unchanged for a missing value and otherwise
        converts the ``Decimal`` to its exact string representation,
        avoiding any floating-point rounding.
        """
        if value is None:
            return None
        return str(value)

    @classmethod
    def from_domain(
        cls,
        fundamentals: CompanyFundamentals,
    ) -> "CompanyFundamentalsResponse":
        """Convert a domain ``CompanyFundamentals`` into its API response shape.

        Maps fields directly and explicitly, with no recalculation,
        rounding, scaling, or reformatting of values, and no
        substitution of missing optional values.
        """
        return cls(
            symbol=fundamentals.symbol,
            displaySymbol=fundamentals.display_symbol,
            companyName=fundamentals.company_name,
            exchange=fundamentals.exchange,
            sector=fundamentals.sector,
            industry=fundamentals.industry,
            website=fundamentals.website,
            businessSummary=fundamentals.business_summary,
            marketCap=fundamentals.market_cap,
            enterpriseValue=fundamentals.enterprise_value,
            trailingPE=fundamentals.trailing_pe,
            forwardPE=fundamentals.forward_pe,
            priceToBook=fundamentals.price_to_book,
            enterpriseToRevenue=fundamentals.enterprise_to_revenue,
            enterpriseToEbitda=fundamentals.enterprise_to_ebitda,
            trailingEps=fundamentals.trailing_eps,
            forwardEps=fundamentals.forward_eps,
            bookValuePerShare=fundamentals.book_value_per_share,
            returnOnEquity=fundamentals.return_on_equity,
            returnOnAssets=fundamentals.return_on_assets,
            profitMargin=fundamentals.profit_margin,
            operatingMargin=fundamentals.operating_margin,
            revenueGrowth=fundamentals.revenue_growth,
            earningsGrowth=fundamentals.earnings_growth,
            totalRevenue=fundamentals.total_revenue,
            netIncome=fundamentals.net_income,
            totalCash=fundamentals.total_cash,
            totalDebt=fundamentals.total_debt,
            debtToEquity=fundamentals.debt_to_equity,
            freeCashFlow=fundamentals.free_cash_flow,
            operatingCashFlow=fundamentals.operating_cash_flow,
            dividendRate=fundamentals.dividend_rate,
            dividendYield=fundamentals.dividend_yield,
            payoutRatio=fundamentals.payout_ratio,
            fiftyTwoWeekHigh=fundamentals.fifty_two_week_high,
            fiftyTwoWeekLow=fundamentals.fifty_two_week_low,
            fiftyDayAverage=fundamentals.fifty_day_average,
            twoHundredDayAverage=fundamentals.two_hundred_day_average,
            currency=fundamentals.currency,
            fetchedAt=fundamentals.fetched_at,
        )