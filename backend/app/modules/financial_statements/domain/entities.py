"""Domain entities for the financial_statements module."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from app.modules.stock_search.domain.entities import StockExchange


class FinancialStatementPeriod(StrEnum):
    """Supported financial-statement reporting periods."""

    ANNUAL = "annual"
    QUARTERLY = "quarterly"


class FinancialStatementsFreshnessStatus(StrEnum):
    """Heuristic freshness state for provider statement data."""

    CURRENT = "current"
    POTENTIALLY_STALE = "potentially_stale"


@dataclass(frozen=True, slots=True)
class FinancialStatementRecord:
    """Financial values reported for one statement date.

    Missing provider values remain ``None``. Monetary values use
    ``Decimal`` and are not rounded, scaled, estimated, or reformatted.
    """

    reporting_date: date

    # Income statement
    total_revenue: Decimal | None
    gross_profit: Decimal | None
    operating_income: Decimal | None
    ebitda: Decimal | None
    net_income: Decimal | None
    diluted_eps: Decimal | None

    # Balance sheet
    total_assets: Decimal | None
    total_liabilities: Decimal | None
    shareholder_equity: Decimal | None
    cash_and_equivalents: Decimal | None
    total_debt: Decimal | None

    # Cash-flow statement
    operating_cash_flow: Decimal | None
    capital_expenditure: Decimal | None
    free_cash_flow: Decimal | None
    investing_cash_flow: Decimal | None
    financing_cash_flow: Decimal | None


@dataclass(frozen=True, slots=True)
class FinancialStatements:
    """Normalised company financial statements across reporting periods."""

    symbol: str
    display_symbol: str
    company_name: str
    exchange: StockExchange
    period: FinancialStatementPeriod
    currency: str | None
    statements: tuple[FinancialStatementRecord, ...]

    latest_reporting_date: date
    expected_latest_reporting_date: date
    data_age_days: int
    freshness_status: FinancialStatementsFreshnessStatus
    is_potentially_stale: bool

    fetched_at: datetime
