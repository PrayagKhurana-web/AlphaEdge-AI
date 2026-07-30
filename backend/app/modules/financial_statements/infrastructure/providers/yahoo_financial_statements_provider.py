"""Yahoo Finance provider for the financial_statements module."""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Final, NoReturn

import httpx
import pandas as pd
import yfinance as yf

from app.modules.financial_statements.application.ports import (
    FinancialStatementsProviderPort,
)
from app.modules.financial_statements.domain.entities import (
    FinancialStatementPeriod,
    FinancialStatementRecord,
    FinancialStatements,
    FinancialStatementsFreshnessStatus,
)
from app.modules.financial_statements.domain.exceptions import (
    FinancialStatementsProviderRateLimitedError,
    FinancialStatementsProviderTimeoutError,
    FinancialStatementsProviderUnavailableError,
    InvalidFinancialStatementsDataError,
    InvalidFinancialStatementsRequestError,
)
from app.modules.stock_search.domain.entities import StockExchange


_EXCHANGE_TOKEN_TO_YAHOO_SUFFIX: Final[dict[str, str]] = {
    "NSE": ".NS",
    "BSE": ".BO",
}

_PROVIDER_NAME: Final[str] = "YahooFinancialStatementsProvider"


class YahooFinancialStatementsProvider(FinancialStatementsProviderPort):
    """Retrieve annual or quarterly financial statements through yfinance."""

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        request_timeout_seconds: float,
    ) -> None:
        self._http_client = http_client
        self._request_timeout_seconds = request_timeout_seconds

    async def get_financial_statements(
        self,
        display_symbol: str,
        period: FinancialStatementPeriod,
    ) -> FinancialStatements:
        canonical_symbol, exchange_token = self._split_display_symbol(
            display_symbol
        )
        normalized_display_symbol = (
            f"{canonical_symbol}.{exchange_token}"
        )
        yahoo_symbol = self._to_yahoo_symbol(
            canonical_symbol,
            exchange_token,
        )

        try:
            payload = await asyncio.wait_for(
                asyncio.to_thread(
                    self._fetch_statements,
                    yahoo_symbol,
                    period,
                ),
                timeout=self._request_timeout_seconds,
            )
        except TimeoutError as exc:
            raise FinancialStatementsProviderTimeoutError(
                f"{_PROVIDER_NAME}: request timed out for "
                f"{normalized_display_symbol!r}."
            ) from exc
        except (
            InvalidFinancialStatementsDataError,
            FinancialStatementsProviderRateLimitedError,
            FinancialStatementsProviderTimeoutError,
            FinancialStatementsProviderUnavailableError,
        ):
            raise
        except Exception as exc:
            self._translate_provider_exception(
                exc,
                display_symbol=normalized_display_symbol,
            )

        income, balance_sheet, cash_flow, info = payload

        return self._to_domain_entity(
            income=income,
            balance_sheet=balance_sheet,
            cash_flow=cash_flow,
            info=info,
            canonical_symbol=canonical_symbol,
            display_symbol=normalized_display_symbol,
            exchange_token=exchange_token,
            period=period,
        )

    def _fetch_statements(
        self,
        yahoo_symbol: str,
        period: FinancialStatementPeriod,
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
        try:
            ticker = yf.Ticker(yahoo_symbol)

            if period is FinancialStatementPeriod.ANNUAL:
                income = ticker.financials
                balance_sheet = ticker.balance_sheet
                cash_flow = ticker.cashflow
            else:
                income = ticker.quarterly_financials
                balance_sheet = ticker.quarterly_balance_sheet
                cash_flow = ticker.quarterly_cashflow

            info = ticker.info
        except Exception as exc:
            self._translate_provider_exception(
                exc,
                display_symbol=yahoo_symbol,
            )

        if (
            not isinstance(income, pd.DataFrame)
            or not isinstance(balance_sheet, pd.DataFrame)
            or not isinstance(cash_flow, pd.DataFrame)
        ):
            raise InvalidFinancialStatementsDataError(
                f"{_PROVIDER_NAME}: provider returned invalid statement "
                f"objects for {yahoo_symbol!r}."
            )

        if income.empty and balance_sheet.empty and cash_flow.empty:
            raise InvalidFinancialStatementsDataError(
                f"{_PROVIDER_NAME}: provider returned no usable statements "
                f"for {yahoo_symbol!r}."
            )

        if not isinstance(info, dict):
            info = {}

        return income, balance_sheet, cash_flow, info

    def _to_domain_entity(
        self,
        *,
        income: pd.DataFrame,
        balance_sheet: pd.DataFrame,
        cash_flow: pd.DataFrame,
        info: dict[str, Any],
        canonical_symbol: str,
        display_symbol: str,
        exchange_token: str,
        period: FinancialStatementPeriod,
    ) -> FinancialStatements:
        reporting_dates = sorted(
            {
                self._normalise_column_date(column)
                for frame in (income, balance_sheet, cash_flow)
                for column in frame.columns
                if self._normalise_column_date(column) is not None
            },
            reverse=True,
        )

        records: list[FinancialStatementRecord] = []

        for reporting_date in reporting_dates[:4]:
            records.append(
                FinancialStatementRecord(
                    reporting_date=reporting_date,
                    total_revenue=self._get_value(
                        income,
                        reporting_date,
                        "Total Revenue",
                    ),
                    gross_profit=self._get_value(
                        income,
                        reporting_date,
                        "Gross Profit",
                    ),
                    operating_income=self._get_value(
                        income,
                        reporting_date,
                        "Operating Income",
                    ),
                    ebitda=self._get_value(
                        income,
                        reporting_date,
                        "EBITDA",
                    ),
                    net_income=self._get_value(
                        income,
                        reporting_date,
                        "Net Income",
                    ),
                    diluted_eps=self._get_value(
                        income,
                        reporting_date,
                        "Diluted EPS",
                    ),
                    total_assets=self._get_value(
                        balance_sheet,
                        reporting_date,
                        "Total Assets",
                    ),
                    total_liabilities=self._get_value(
                        balance_sheet,
                        reporting_date,
                        "Total Liabilities Net Minority Interest",
                    ),
                    shareholder_equity=self._get_value(
                        balance_sheet,
                        reporting_date,
                        "Stockholders Equity",
                        "Common Stock Equity",
                    ),
                    cash_and_equivalents=self._get_value(
                        balance_sheet,
                        reporting_date,
                        "Cash Cash Equivalents And Short Term Investments",
                        "Cash And Cash Equivalents",
                    ),
                    total_debt=self._get_value(
                        balance_sheet,
                        reporting_date,
                        "Total Debt",
                    ),
                    operating_cash_flow=self._get_value(
                        cash_flow,
                        reporting_date,
                        "Operating Cash Flow",
                    ),
                    capital_expenditure=self._get_value(
                        cash_flow,
                        reporting_date,
                        "Capital Expenditure",
                        "Capital Expenditure Reported",
                    ),
                    free_cash_flow=self._get_value(
                        cash_flow,
                        reporting_date,
                        "Free Cash Flow",
                    ),
                    investing_cash_flow=self._get_value(
                        cash_flow,
                        reporting_date,
                        "Investing Cash Flow",
                    ),
                    financing_cash_flow=self._get_value(
                        cash_flow,
                        reporting_date,
                        "Financing Cash Flow",
                    ),
                )
            )

        usable_records = tuple(
            record
            for record in records
            if self._record_has_data(record)
        )

        if not usable_records:
            raise InvalidFinancialStatementsDataError(
                f"{_PROVIDER_NAME}: no supported financial statement "
                f"fields were available for {display_symbol!r}."
            )

        exchange = StockExchange(exchange_token)

        company_name = (
            self._optional_text(info.get("longName"))
            or self._optional_text(info.get("shortName"))
            or canonical_symbol
        )

        currency = (
            self._optional_text(info.get("financialCurrency"))
            or self._optional_text(info.get("currency"))
        )

        fetched_at = datetime.now(timezone.utc)
        latest_reporting_date = usable_records[0].reporting_date

        expected_latest_reporting_date = (
            self._expected_latest_reporting_date(
                period=period,
                as_of=fetched_at.date(),
            )
        )

        data_age_days = max(
            0,
            (fetched_at.date() - latest_reporting_date).days,
        )

        is_potentially_stale = (
            latest_reporting_date
            < expected_latest_reporting_date
        )

        freshness_status = (
            FinancialStatementsFreshnessStatus.POTENTIALLY_STALE
            if is_potentially_stale
            else FinancialStatementsFreshnessStatus.CURRENT
        )

        return FinancialStatements(
            symbol=canonical_symbol,
            display_symbol=display_symbol,
            company_name=company_name,
            exchange=exchange,
            period=period,
            currency=currency,
            statements=usable_records,
            latest_reporting_date=latest_reporting_date,
            expected_latest_reporting_date=(
                expected_latest_reporting_date
            ),
            data_age_days=data_age_days,
            freshness_status=freshness_status,
            is_potentially_stale=is_potentially_stale,
            fetched_at=fetched_at,
        )

    @staticmethod
    def _expected_latest_reporting_date(
        *,
        period: FinancialStatementPeriod,
        as_of: date,
    ) -> date:
        """Return the latest expected reporting period after a grace window."""
        grace_days = (
            30
            if period is FinancialStatementPeriod.QUARTERLY
            else 120
        )

        cutoff = as_of - timedelta(days=grace_days)

        if period is FinancialStatementPeriod.ANNUAL:
            candidate = date(cutoff.year, 3, 31)

            if candidate > cutoff:
                candidate = date(cutoff.year - 1, 3, 31)

            return candidate

        candidates = [
            date(year, month, day)
            for year in range(cutoff.year - 1, cutoff.year + 1)
            for month, day in (
                (3, 31),
                (6, 30),
                (9, 30),
                (12, 31),
            )
            if date(year, month, day) <= cutoff
        ]

        return max(candidates)

    def _get_value(
        self,
        frame: pd.DataFrame,
        reporting_date: Any,
        *row_names: str,
    ) -> Decimal | None:
        if frame.empty:
            return None

        matching_column = next(
            (
                column
                for column in frame.columns
                if self._normalise_column_date(column) == reporting_date
            ),
            None,
        )

        if matching_column is None:
            return None

        for row_name in row_names:
            if row_name not in frame.index:
                continue

            value = frame.at[row_name, matching_column]
            converted = self._to_optional_decimal(value)

            if converted is not None:
                return converted

        return None

    @staticmethod
    def _normalise_column_date(value: Any) -> Any:
        try:
            return pd.Timestamp(value).date()
        except Exception:
            return None

    @staticmethod
    def _to_optional_decimal(value: Any) -> Decimal | None:
        if value is None or pd.isna(value):
            return None

        try:
            converted = Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError):
            return None

        if not converted.is_finite():
            return None

        return converted

    @staticmethod
    def _optional_text(value: Any) -> str | None:
        if not isinstance(value, str):
            return None

        normalized = value.strip()
        return normalized or None

    @staticmethod
    def _record_has_data(record: FinancialStatementRecord) -> bool:
        return any(
            value is not None
            for value in (
                record.total_revenue,
                record.gross_profit,
                record.operating_income,
                record.ebitda,
                record.net_income,
                record.diluted_eps,
                record.total_assets,
                record.total_liabilities,
                record.shareholder_equity,
                record.cash_and_equivalents,
                record.total_debt,
                record.operating_cash_flow,
                record.capital_expenditure,
                record.free_cash_flow,
                record.investing_cash_flow,
                record.financing_cash_flow,
            )
        )

    @staticmethod
    def _split_display_symbol(
        display_symbol: str,
    ) -> tuple[str, str]:
        normalized = display_symbol.strip().upper()

        if normalized.count(".") != 1:
            raise InvalidFinancialStatementsRequestError(
                "Display symbol must use SYMBOL.EXCHANGE format."
            )

        symbol, exchange = normalized.rsplit(".", 1)

        if not symbol or exchange not in _EXCHANGE_TOKEN_TO_YAHOO_SUFFIX:
            raise InvalidFinancialStatementsRequestError(
                "Only NSE and BSE display symbols are supported."
            )

        return symbol, exchange

    @staticmethod
    def _to_yahoo_symbol(
        canonical_symbol: str,
        exchange_token: str,
    ) -> str:
        return (
            f"{canonical_symbol}"
            f"{_EXCHANGE_TOKEN_TO_YAHOO_SUFFIX[exchange_token]}"
        )

    def _translate_provider_exception(
        self,
        exc: Exception,
        *,
        display_symbol: str,
    ) -> NoReturn:
        exception_name = type(exc).__name__.lower()
        exception_message = str(exc).lower()

        if (
            "ratelimit" in exception_name
            or "rate limit" in exception_message
            or "too many requests" in exception_message
            or "429" in exception_message
        ):
            raise FinancialStatementsProviderRateLimitedError(
                f"{_PROVIDER_NAME}: rate-limited for "
                f"{display_symbol!r}.",
                retry_after_seconds=None,
            ) from exc

        if (
            "timeout" in exception_name
            or "timed out" in exception_message
        ):
            raise FinancialStatementsProviderTimeoutError(
                f"{_PROVIDER_NAME}: timed out for "
                f"{display_symbol!r}."
            ) from exc

        raise FinancialStatementsProviderUnavailableError(
            f"{_PROVIDER_NAME}: provider unavailable for "
            f"{display_symbol!r}."
        ) from exc
