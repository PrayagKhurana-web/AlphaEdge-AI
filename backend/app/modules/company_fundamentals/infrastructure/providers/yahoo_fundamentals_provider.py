"""
Yahoo Finance implementation of FundamentalsProviderPort.

This adapter retrieves company fundamentals through yfinance, which
handles Yahoo Finance's cookie and crumb authentication internally.

All Yahoo-specific field names and symbol conventions remain isolated
inside this infrastructure adapter. The application and domain layers
continue to depend only on FundamentalsProviderPort and
CompanyFundamentals.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Final, NoReturn

import httpx
import yfinance as yf

from app.modules.company_fundamentals.application.ports import (
    FundamentalsProviderPort,
)
from app.modules.company_fundamentals.domain.entities import (
    CompanyFundamentals,
)
from app.modules.company_fundamentals.domain.exceptions import (
    FundamentalsProviderRateLimitedError,
    FundamentalsProviderTimeoutError,
    FundamentalsProviderUnavailableError,
    InvalidFundamentalsDataError,
    InvalidFundamentalsRequestError,
)
from app.modules.stock_search.domain.entities import StockExchange


_EXCHANGE_TOKEN_TO_YAHOO_SUFFIX: Final[dict[str, str]] = {
    "NSE": ".NS",
    "BSE": ".BO",
}

_PROVIDER_NAME: Final[str] = "YahooFundamentalsProvider"


class YahooFundamentalsProvider(FundamentalsProviderPort):
    """
    Fundamentals provider backed by Yahoo Finance through yfinance.

    The existing ``http_client`` constructor argument is retained so the
    module's current dependency wiring remains compatible. yfinance owns
    its internal Yahoo session, so the injected client is not used for
    fundamentals retrieval.

    yfinance performs blocking network work. Calls are therefore executed
    through ``asyncio.to_thread`` so they do not block FastAPI's event
    loop.
    """

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        request_timeout_seconds: float,
    ) -> None:
        """
        Args:
            http_client:
                Existing module-owned client retained for compatibility
                with the current dependency wiring.
            request_timeout_seconds:
                Maximum number of seconds allowed for a fundamentals
                request.
        """
        self._http_client = http_client
        self._request_timeout_seconds = request_timeout_seconds

    async def get_fundamentals(
        self,
        display_symbol: str,
    ) -> CompanyFundamentals:
        """
        Fetch a point-in-time fundamentals snapshot for a display symbol.

        Args:
            display_symbol:
                Public symbol in ``SYMBOL.EXCHANGE`` format, such as
                ``RELIANCE.NSE`` or ``500325.BSE``.

        Returns:
            Normalized CompanyFundamentals domain entity.

        Raises:
            InvalidFundamentalsRequestError:
                If the display symbol is malformed or its exchange is
                unsupported.
            FundamentalsProviderTimeoutError:
                If retrieval exceeds the configured timeout.
            FundamentalsProviderRateLimitedError:
                If Yahoo Finance rate-limits the request.
            FundamentalsProviderUnavailableError:
                If Yahoo Finance cannot be reached or fails.
            InvalidFundamentalsDataError:
                If Yahoo returns no usable fundamentals snapshot.
        """
        canonical_symbol, exchange_token = self._split_display_symbol(
            display_symbol
        )

        normalized_display_symbol = (
            f"{canonical_symbol}.{exchange_token}"
        )

        yahoo_symbol = self._to_yahoo_symbol(
            canonical_symbol,
            exchange_token,
            display_symbol=normalized_display_symbol,
        )

        try:
            info = await asyncio.wait_for(
                asyncio.to_thread(
                    self._fetch_yfinance_info,
                    yahoo_symbol,
                ),
                timeout=self._request_timeout_seconds,
            )
        except TimeoutError as exc:
            raise FundamentalsProviderTimeoutError(
                f"{_PROVIDER_NAME}: Yahoo Finance request timed out after "
                f"{self._request_timeout_seconds} second(s) for "
                f"display_symbol {normalized_display_symbol!r}."
            ) from exc
        except (
            InvalidFundamentalsDataError,
            FundamentalsProviderRateLimitedError,
            FundamentalsProviderTimeoutError,
            FundamentalsProviderUnavailableError,
        ):
            raise
        except Exception as exc:
            self._translate_provider_exception(
                exc,
                display_symbol=normalized_display_symbol,
            )

        return self._to_domain_entity(
            info,
            display_symbol=normalized_display_symbol,
            canonical_symbol=canonical_symbol,
            exchange_token=exchange_token,
        )

    def _fetch_yfinance_info(
        self,
        yahoo_symbol: str,
    ) -> dict[str, Any]:
        """
        Fetch Yahoo's flattened company-information dictionary.

        This function is synchronous because yfinance is synchronous. It
        is called from a worker thread by ``get_fundamentals``.
        """
        try:
            ticker = yf.Ticker(yahoo_symbol)
            info = ticker.info
        except Exception as exc:
            self._translate_provider_exception(
                exc,
                display_symbol=yahoo_symbol,
            )

        if not isinstance(info, dict) or not info:
            raise InvalidFundamentalsDataError(
                f"{_PROVIDER_NAME}: Yahoo Finance returned no usable "
                f"fundamentals data for symbol {yahoo_symbol!r}."
            )

        return info

    def _translate_provider_exception(
        self,
        exc: Exception,
        *,
        display_symbol: str,
    ) -> NoReturn:
        """
        Translate yfinance and underlying network errors into the module's
        approved domain exceptions.

        Raw provider details remain inside the exception chain and are not
        exposed by the API response.
        """
        exception_name = type(exc).__name__.lower()
        exception_message = str(exc).lower()

        if (
            "ratelimit" in exception_name
            or "rate limit" in exception_message
            or "too many requests" in exception_message
            or "429" in exception_message
        ):
            raise FundamentalsProviderRateLimitedError(
                f"{_PROVIDER_NAME}: Yahoo Finance rate-limited the "
                f"request for display_symbol {display_symbol!r}.",
                retry_after_seconds=None,
            ) from exc

        if (
            "timeout" in exception_name
            or "timed out" in exception_message
            or "operation timed out" in exception_message
        ):
            raise FundamentalsProviderTimeoutError(
                f"{_PROVIDER_NAME}: Yahoo Finance timed out while "
                f"retrieving display_symbol {display_symbol!r}."
            ) from exc

        raise FundamentalsProviderUnavailableError(
            f"{_PROVIDER_NAME}: Yahoo Finance was unavailable while "
            f"retrieving display_symbol {display_symbol!r}."
        ) from exc

    def _split_display_symbol(
        self,
        display_symbol: str,
    ) -> tuple[str, str]:
        """
        Validate and normalize a ``SYMBOL.EXCHANGE`` display symbol.
        """
        if not isinstance(display_symbol, str) or not display_symbol.strip():
            raise InvalidFundamentalsRequestError(
                f"{_PROVIDER_NAME}: display_symbol must be a non-empty "
                "string."
            )

        trimmed_display_symbol = display_symbol.strip()

        canonical_symbol, separator, exchange_token = (
            trimmed_display_symbol.rpartition(".")
        )

        if (
            not separator
            or not canonical_symbol.strip()
            or not exchange_token.strip()
        ):
            raise InvalidFundamentalsRequestError(
                f"{_PROVIDER_NAME}: display_symbol {display_symbol!r} is "
                "not in the expected 'SYMBOL.EXCHANGE' format."
            )

        return (
            canonical_symbol.strip().upper(),
            exchange_token.strip().upper(),
        )

    def _to_yahoo_symbol(
        self,
        canonical_symbol: str,
        exchange_token: str,
        *,
        display_symbol: str,
    ) -> str:
        """
        Convert the public symbol into Yahoo Finance's ticker format.

        Examples:
            RELIANCE.NSE -> RELIANCE.NS
            500325.BSE -> 500325.BO
        """
        try:
            yahoo_suffix = _EXCHANGE_TOKEN_TO_YAHOO_SUFFIX[exchange_token]
        except KeyError as exc:
            raise InvalidFundamentalsRequestError(
                f"{_PROVIDER_NAME}: display_symbol {display_symbol!r} has "
                f"unsupported exchange token {exchange_token!r}."
            ) from exc

        return f"{canonical_symbol}{yahoo_suffix}"

    def _to_domain_entity(
        self,
        info: dict[str, Any],
        *,
        display_symbol: str,
        canonical_symbol: str,
        exchange_token: str,
    ) -> CompanyFundamentals:
        """
        Convert yfinance's flattened information dictionary into the
        CompanyFundamentals domain entity.
        """
        company_name = self._resolve_company_name(
            info,
            display_symbol=display_symbol,
        )

        exchange = self._to_stock_exchange(
            exchange_token,
            display_symbol=display_symbol,
        )

        return CompanyFundamentals(
            symbol=canonical_symbol,
            display_symbol=display_symbol,
            company_name=company_name,
            exchange=exchange,
            sector=self._to_optional_str(
                info.get("sector")
            ),
            industry=self._to_optional_str(
                info.get("industry")
            ),
            website=self._to_optional_str(
                info.get("website")
            ),
            business_summary=self._to_optional_str(
                info.get("longBusinessSummary")
            ),

            market_cap=self._to_optional_decimal(
                info.get("marketCap")
            ),
            enterprise_value=self._to_optional_decimal(
                info.get("enterpriseValue")
            ),
            trailing_pe=self._to_optional_decimal(
                info.get("trailingPE")
            ),
            forward_pe=self._to_optional_decimal(
                info.get("forwardPE")
            ),
            price_to_book=self._to_optional_decimal(
                info.get("priceToBook")
            ),
            enterprise_to_revenue=self._to_optional_decimal(
                info.get("enterpriseToRevenue")
            ),
            enterprise_to_ebitda=self._to_optional_decimal(
                info.get("enterpriseToEbitda")
            ),

            trailing_eps=self._to_optional_decimal(
                info.get("trailingEps")
            ),
            forward_eps=self._to_optional_decimal(
                info.get("forwardEps")
            ),
            book_value_per_share=self._to_optional_decimal(
                info.get("bookValue")
            ),
            return_on_equity=self._to_optional_decimal(
                info.get("returnOnEquity")
            ),
            return_on_assets=self._to_optional_decimal(
                info.get("returnOnAssets")
            ),
            profit_margin=self._to_optional_decimal(
                info.get("profitMargins")
            ),
            operating_margin=self._to_optional_decimal(
                info.get("operatingMargins")
            ),

            revenue_growth=self._to_optional_decimal(
                info.get("revenueGrowth")
            ),
            earnings_growth=self._to_optional_decimal(
                info.get("earningsGrowth")
            ),

            total_revenue=self._to_optional_decimal(
                info.get("totalRevenue")
            ),
            net_income=self._to_optional_decimal(
                info.get("netIncomeToCommon")
            ),
            total_cash=self._to_optional_decimal(
                info.get("totalCash")
            ),
            total_debt=self._to_optional_decimal(
                info.get("totalDebt")
            ),
            debt_to_equity=self._to_optional_decimal(
                info.get("debtToEquity")
            ),
            free_cash_flow=self._to_optional_decimal(
                info.get("freeCashflow")
            ),
            operating_cash_flow=self._to_optional_decimal(
                info.get("operatingCashflow")
            ),

            dividend_rate=self._to_optional_decimal(
                info.get("dividendRate")
            ),
            dividend_yield=self._to_optional_decimal(
                info.get("dividendYield")
            ),
            payout_ratio=self._to_optional_decimal(
                info.get("payoutRatio")
            ),

            fifty_two_week_high=self._to_optional_decimal(
                info.get("fiftyTwoWeekHigh")
            ),
            fifty_two_week_low=self._to_optional_decimal(
                info.get("fiftyTwoWeekLow")
            ),
            fifty_day_average=self._to_optional_decimal(
                info.get("fiftyDayAverage")
            ),
            two_hundred_day_average=self._to_optional_decimal(
                info.get("twoHundredDayAverage")
            ),

            currency=self._to_optional_str(
                info.get("currency")
            ),
            fetched_at=datetime.now(timezone.utc),
        )

    def _to_stock_exchange(
        self,
        exchange_token: str,
        *,
        display_symbol: str,
    ) -> StockExchange:
        """
        Convert an exchange token into the shared StockExchange enum.
        """
        try:
            return StockExchange(exchange_token)
        except ValueError as exc:
            raise InvalidFundamentalsDataError(
                f"{_PROVIDER_NAME}: exchange token {exchange_token!r} "
                f"for display_symbol {display_symbol!r} could not be "
                "converted to a valid StockExchange."
            ) from exc

    def _to_optional_decimal(
        self,
        raw_value: Any,
    ) -> Decimal | None:
        """
        Safely convert an optional provider value to Decimal.

        Missing, Boolean, malformed, NaN, and infinite values become None.
        """
        if raw_value is None or isinstance(raw_value, bool):
            return None

        try:
            decimal_value = Decimal(str(raw_value))
        except (InvalidOperation, ValueError, TypeError):
            return None

        if not decimal_value.is_finite():
            return None

        return decimal_value

    def _to_optional_str(
        self,
        raw_value: Any,
    ) -> str | None:
        """
        Convert a provider value into a trimmed, non-empty optional string.
        """
        if not isinstance(raw_value, str):
            return None

        stripped_value = raw_value.strip()
        return stripped_value or None

    def _resolve_company_name(
        self,
        info: dict[str, Any],
        *,
        display_symbol: str,
    ) -> str:
        """
        Resolve the company name, preferring longName over shortName.
        """
        for field_name in ("longName", "shortName"):
            candidate = info.get(field_name)

            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()

        raise InvalidFundamentalsDataError(
            f"{_PROVIDER_NAME}: Yahoo Finance did not return a usable "
            f"company name for display_symbol {display_symbol!r}."
        )