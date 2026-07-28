"""API schemas for the financial_statements module."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_serializer

from app.modules.financial_statements.domain.entities import (
    FinancialStatementRecord,
    FinancialStatements,
)


class FinancialStatementRecordResponse(BaseModel):
    """One reporting-period financial statement record."""

    model_config = ConfigDict(
        populate_by_name=True,
        serialize_by_alias=True,
    )

    reporting_date: date = Field(alias="reportingDate")

    total_revenue: Decimal | None = Field(alias="totalRevenue")
    gross_profit: Decimal | None = Field(alias="grossProfit")
    operating_income: Decimal | None = Field(alias="operatingIncome")
    ebitda: Decimal | None
    net_income: Decimal | None = Field(alias="netIncome")
    diluted_eps: Decimal | None = Field(alias="dilutedEps")

    total_assets: Decimal | None = Field(alias="totalAssets")
    total_liabilities: Decimal | None = Field(alias="totalLiabilities")
    shareholder_equity: Decimal | None = Field(alias="shareholderEquity")
    cash_and_equivalents: Decimal | None = Field(alias="cashAndEquivalents")
    total_debt: Decimal | None = Field(alias="totalDebt")

    operating_cash_flow: Decimal | None = Field(alias="operatingCashFlow")
    capital_expenditure: Decimal | None = Field(alias="capitalExpenditure")
    free_cash_flow: Decimal | None = Field(alias="freeCashFlow")
    investing_cash_flow: Decimal | None = Field(alias="investingCashFlow")
    financing_cash_flow: Decimal | None = Field(alias="financingCashFlow")

    @field_serializer(
        "total_revenue",
        "gross_profit",
        "operating_income",
        "ebitda",
        "net_income",
        "diluted_eps",
        "total_assets",
        "total_liabilities",
        "shareholder_equity",
        "cash_and_equivalents",
        "total_debt",
        "operating_cash_flow",
        "capital_expenditure",
        "free_cash_flow",
        "investing_cash_flow",
        "financing_cash_flow",
        when_used="json",
    )
    def serialize_decimal_fields(
        self,
        value: Decimal | None,
    ) -> str | None:
        if value is None:
            return None
        return str(value)

    @classmethod
    def from_domain(
        cls,
        record: FinancialStatementRecord,
    ) -> "FinancialStatementRecordResponse":
        return cls(
            reportingDate=record.reporting_date,
            totalRevenue=record.total_revenue,
            grossProfit=record.gross_profit,
            operatingIncome=record.operating_income,
            ebitda=record.ebitda,
            netIncome=record.net_income,
            dilutedEps=record.diluted_eps,
            totalAssets=record.total_assets,
            totalLiabilities=record.total_liabilities,
            shareholderEquity=record.shareholder_equity,
            cashAndEquivalents=record.cash_and_equivalents,
            totalDebt=record.total_debt,
            operatingCashFlow=record.operating_cash_flow,
            capitalExpenditure=record.capital_expenditure,
            freeCashFlow=record.free_cash_flow,
            investingCashFlow=record.investing_cash_flow,
            financingCashFlow=record.financing_cash_flow,
        )


class FinancialStatementsResponse(BaseModel):
    """Financial statements returned by the API."""

    model_config = ConfigDict(
        populate_by_name=True,
        serialize_by_alias=True,
    )

    symbol: str
    display_symbol: str = Field(alias="displaySymbol")
    company_name: str = Field(alias="companyName")
    exchange: str
    period: str
    currency: str | None
    statements: list[FinancialStatementRecordResponse]
    fetched_at: AwareDatetime = Field(alias="fetchedAt")

    @classmethod
    def from_domain(
        cls,
        financial_statements: FinancialStatements,
    ) -> "FinancialStatementsResponse":
        return cls(
            symbol=financial_statements.symbol,
            displaySymbol=financial_statements.display_symbol,
            companyName=financial_statements.company_name,
            exchange=financial_statements.exchange.value,
            period=financial_statements.period.value,
            currency=financial_statements.currency,
            statements=[
                FinancialStatementRecordResponse.from_domain(record)
                for record in financial_statements.statements
            ],
            fetchedAt=financial_statements.fetched_at,
        )
