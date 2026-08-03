"""
Yahoo Finance implementation of StockSearchProviderPort.

This is the only file in the stock_search module that knows Yahoo
Finance's search endpoint URL, request/response shape, or field names --
every other layer depends solely on StockSearchProviderPort and this
module's own domain entities/exceptions. Swapping to a different search
backend later means adding a new class here that satisfies the same port;
it requires no change to application/services.py or the API layer.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Final, Literal

import httpx

from app.modules.stock_search.application.ports import StockSearchProviderPort
from app.modules.stock_search.domain.entities import (
    StockExchange,
    StockSearchResult,
    StockSearchResults,
)
from app.modules.stock_search.domain.exceptions import (
    InvalidSearchResultError,
    SearchProviderRateLimitedError,
    SearchProviderTimeoutError,
    SearchProviderUnavailableError,
)

logger = logging.getLogger(__name__)

# Yahoo Finance's search endpoint. Kept private to this adapter -- no
# other file in the codebase should ever reference this URL.
_SEARCH_ENDPOINT_URL: Final[str] = "https://query1.finance.yahoo.com/v1/finance/search"

# A browser-like User-Agent is required; Yahoo's endpoints reject requests
# that look like a bare script client.
_REQUEST_HEADERS: Final[dict[str, str]] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

# Yahoo symbol suffixes for the two exchanges this module supports,
# mapped to the domain's StockExchange enum. Kept private to this adapter
# per the rule that provider-specific symbol conventions never leak
# outside it.
_SUFFIX_TO_EXCHANGE: Final[dict[str, StockExchange]] = {
    ".NS": StockExchange.NSE,
    ".BO": StockExchange.BSE,
}

# The only Yahoo quoteType value this module treats as a parseable result
# -- any other well-formed string value (ETF, MUTUALFUND, INDEX, CURRENCY,
# CRYPTOCURRENCY, FUTURE, OPTION, etc.) is an intentional exclusion, not a
# malformed entry.
_SUPPORTED_QUOTE_TYPE: Final[str] = "EQUITY"

_QuoteClassification = Literal["equity", "excluded", "malformed"]


class YahooStockSearchProvider(StockSearchProviderPort):
    """
    StockSearchProviderPort implementation backed by Yahoo Finance's
    public search endpoint, restricted to Indian equities listed on NSE
    or BSE.

    A single httpx.AsyncClient is injected via the constructor and reused
    across calls, so connection pooling/keep-alive is handled by the
    caller's client configuration rather than by this class -- this class
    never constructs its own client.
    """

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        request_timeout_seconds: float,
    ) -> None:
        """
        Args:
            http_client: A shared httpx.AsyncClient instance to issue
                requests through.
            request_timeout_seconds: Per-request timeout, in seconds. Must
                be finite and strictly positive.

        Raises:
            ValueError: if `request_timeout_seconds` is not finite or is
                less than or equal to zero.
        """
        if not math.isfinite(request_timeout_seconds) or request_timeout_seconds <= 0:
            raise ValueError(
                "request_timeout_seconds must be finite and strictly "
                f"positive, got {request_timeout_seconds!r}"
            )
        self._http_client = http_client
        self._request_timeout_seconds = request_timeout_seconds

    async def search(
        self,
        query: str,
        *,
        limit: int,
    ) -> StockSearchResults:
        """
        Searches Yahoo Finance for `query` and returns up to `limit`
        Indian equity matches (NSE or BSE only), in Yahoo's relevance
        order.

        See StockSearchProviderPort.search for the full contract this
        method honors: a valid query matching nothing returns an empty
        StockSearchResults rather than raising, results are deduplicated
        by (exchange, canonical symbol) preserving first occurrence, and
        malformed individual entries are skipped and logged rather than
        failing the whole request -- unless every entry that looked like
        an Indian equity candidate turned out to be malformed, in which
        case InvalidSearchResultError is raised.

        An entry is only ever excluded silently (as "not a candidate at
        all") when its symbol carries no supported NSE/BSE suffix, or when
        it carries a supported suffix and a well-formed, non-EQUITY
        `quoteType` (an intentionally excluded asset type such as an ETF,
        index, or currency). A supported-suffix entry with a missing,
        empty, or non-string `quoteType` is treated as a malformed Indian
        candidate, not silently skipped, so a response consisting only of
        such entries correctly raises InvalidSearchResultError rather than
        returning a misleadingly empty result.
        """
        raw_quotes = await self._fetch_raw_quotes(query, limit)

        seen_keys: set[tuple[StockExchange, str]] = set()
        parsed_results: list[StockSearchResult] = []
        candidate_count = 0
        parsed_count = 0

        for raw_quote in raw_quotes:
            exchange = self._resolve_exchange(raw_quote)
            if exchange is None:
                # No supported NSE/BSE suffix at all -- not an Indian
                # equity candidate, skip silently.
                continue

            classification = self._classify_quote_type(raw_quote)
            if classification == "excluded":
                # A well-formed, non-EQUITY quoteType (ETF, index,
                # currency, etc.) -- an intentional exclusion, not a
                # malformed entry.
                continue

            candidate_count += 1

            if classification == "malformed":
                logger.warning(
                    "stock_search: skipping malformed Indian-equity "
                    "candidate entry from Yahoo Finance search response "
                    "(missing or invalid quoteType)"
                )
                continue

            parsed = self._try_parse_quote(raw_quote, exchange)
            if parsed is None:
                logger.warning(
                    "stock_search: skipping malformed Indian-equity "
                    "candidate entry from Yahoo Finance search response"
                )
                continue

            parsed_count += 1
            dedupe_key = (parsed.exchange, parsed.symbol)
            if dedupe_key in seen_keys:
                continue
            seen_keys.add(dedupe_key)
            parsed_results.append(parsed)

            if len(parsed_results) >= limit:
                break

        if candidate_count > 0 and parsed_count == 0:
            raise InvalidSearchResultError(
                "Every Indian-equity candidate entry in the Yahoo Finance "
                "search response was malformed and could not be parsed.",
                provider_name=type(self).__name__,
                query=query,
            )

        return StockSearchResults.from_iterable(parsed_results[:limit])

    def _classify_quote_type(self, raw_quote: dict[str, Any]) -> _QuoteClassification:
        """
        Classifies a supported-exchange candidate entry's `quoteType`
        field:

          - "equity": `quoteType` is a well-formed, non-empty string equal
            to "EQUITY" (case-insensitive) -- should be parsed normally.
          - "excluded": `quoteType` is a well-formed, non-empty string
            that is *not* "EQUITY" -- an intentionally excluded asset
            type (ETF, mutual fund, index, currency, cryptocurrency,
            future, option, etc.).
          - "malformed": `quoteType` is missing, empty, or not a string
            at all -- this entry claimed a supported NSE/BSE suffix but
            cannot be classified, so it counts as a malformed Indian
            candidate rather than being silently dropped.
        """
        quote_type = raw_quote.get("quoteType")
        if not isinstance(quote_type, str) or not quote_type.strip():
            return "malformed"
        if quote_type.strip().upper() == _SUPPORTED_QUOTE_TYPE:
            return "equity"
        return "excluded"

    async def _fetch_raw_quotes(self, query: str, limit: int) -> list[dict[str, Any]]:
        """
        Issues the HTTP request to Yahoo Finance's search endpoint and
        returns the raw `quotes` list, with every failure mode translated
        into this module's domain exceptions.

        Raises:
            SearchProviderTimeoutError: if the request did not complete in
                time.
            SearchProviderRateLimitedError: if Yahoo responds with HTTP
                429.
            SearchProviderUnavailableError: if Yahoo responds with HTTP
                401, 403, or 5xx, or the request fails at the connection/
                transport level.
            InvalidSearchResultError: if the response body is not valid
                JSON, or does not contain the expected top-level `quotes`
                list structure.
        """
        params = {
            "q": query,
            "quotesCount": str(limit),
            "newsCount": "0",
            "enableFuzzyQuery": "true",
            "quotesQueryId": "tss_match_phrase_query",
        }

        try:
            response = await self._http_client.get(
                _SEARCH_ENDPOINT_URL,
                params=params,
                headers=_REQUEST_HEADERS,
                timeout=self._request_timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            raise SearchProviderTimeoutError(
                f"Request to Yahoo Finance search timed out after "
                f"{self._request_timeout_seconds} second(s).",
                provider_name=type(self).__name__,
            ) from exc
        except httpx.HTTPError as exc:
            raise SearchProviderUnavailableError(
                f"Request to Yahoo Finance search failed at the transport "
                f"level: {exc}",
                provider_name=type(self).__name__,
            ) from exc

        if response.status_code == 429:
            raise SearchProviderRateLimitedError(
                "Yahoo Finance search reported rate limiting (HTTP 429).",
                provider_name=type(self).__name__,
                retry_after_seconds=self._parse_retry_after(response),
            )
        if response.status_code in (401, 403):
            raise SearchProviderUnavailableError(
                f"Yahoo Finance search denied access (HTTP {response.status_code}).",
                provider_name=type(self).__name__,
            )
        if response.status_code >= 500:
            raise SearchProviderUnavailableError(
                f"Yahoo Finance search returned server error "
                f"HTTP {response.status_code}.",
                provider_name=type(self).__name__,
            )
        if response.status_code >= 400:
            raise InvalidSearchResultError(
                f"Yahoo Finance search returned unexpected client error "
                f"HTTP {response.status_code}.",
                provider_name=type(self).__name__,
                query=query,
            )

        return self._extract_quotes_list(response, query=query)

    def _parse_retry_after(self, response: httpx.Response) -> int | None:
        """
        Parses a numeric `Retry-After` header value in seconds, if present,
        well-formed, and non-negative. Returns None otherwise -- a missing,
        malformed, or negative value is treated as "unknown."
        """
        raw_value = response.headers.get("Retry-After")
        if raw_value is None:
            return None
        try:
            parsed_value = int(raw_value)
        except ValueError:
            return None
        if parsed_value < 0:
            return None
        return parsed_value

    def _extract_quotes_list(
        self, response: httpx.Response, *, query: str
    ) -> list[dict[str, Any]]:
        """
        Parses the response body as JSON and returns the top-level
        `quotes` list, filtered to only entries that are themselves
        dicts.

        A genuinely empty `quotes` list is a valid no-results response and
        is returned as-is. However, if `quotes` is non-empty but contains
        zero dict entries (i.e. every entry is some other, unusable
        shape), that is treated as an unusable response as a whole, since
        there is no way to distinguish "no matches" from "a response we
        cannot interpret at all" in that case.

        Raises:
            InvalidSearchResultError: if the body is not valid JSON, the
                top-level `quotes` field is missing or is not a list, or
                `quotes` is non-empty but contains no dict entries.
        """
        try:
            body = response.json()
        except ValueError as exc:
            raise InvalidSearchResultError(
                "Yahoo Finance search response body was not valid JSON.",
                provider_name=type(self).__name__,
                query=query,
            ) from exc

        quotes = body.get("quotes") if isinstance(body, dict) else None
        if not isinstance(quotes, list):
            raise InvalidSearchResultError(
                "Yahoo Finance search response did not contain the "
                "expected top-level 'quotes' list.",
                provider_name=type(self).__name__,
                query=query,
            )

        dict_entries: list[dict[str, Any]] = []
        for entry in quotes:
            if isinstance(entry, dict):
                dict_entries.append(entry)
            else:
                logger.warning(
                    "stock_search: Yahoo Finance search response "
                    "contained a non-dict quote entry and it was discarded"
                )

        if quotes and not dict_entries:
            raise InvalidSearchResultError(
                "Yahoo Finance search response 'quotes' list contained no "
                "usable (dict) entries.",
                provider_name=type(self).__name__,
                query=query,
            )

        return dict_entries

    def _resolve_exchange(self, raw_quote: dict[str, Any]) -> StockExchange | None:
        """
        Determines whether `raw_quote`'s symbol carries a supported Indian
        exchange suffix (.NS for NSE, .BO for BSE), and returns the
        corresponding StockExchange if so.

        Returns None if the symbol is missing, is not a string, or does
        not end with a recognized suffix -- callers treat None as "not an
        Indian-equity candidate," not as a malformed entry, since Yahoo's
        search response legitimately includes non-Indian-exchange results
        that must simply be excluded.
        """
        raw_symbol = raw_quote.get("symbol")
        if not isinstance(raw_symbol, str):
            return None

        for suffix, exchange in _SUFFIX_TO_EXCHANGE.items():
            if raw_symbol.upper().endswith(suffix):
                return exchange

        return None

    def _try_parse_quote(
        self, raw_quote: dict[str, Any], exchange: StockExchange
    ) -> StockSearchResult | None:
        """
        Attempts to parse one raw quote entry (already confirmed to be an
        Indian-equity EQUITY candidate by _resolve_exchange and
        _classify_quote_type) into a StockSearchResult.

        Returns None (rather than raising) if the canonical symbol cannot
        be derived -- this is the "malformed candidate" case tracked by
        the caller to decide whether InvalidSearchResultError should
        ultimately be raised for the whole request.
        """
        raw_symbol = raw_quote.get("symbol")
        if not isinstance(raw_symbol, str):
            return None

        canonical_symbol = self._normalize_symbol(raw_symbol, exchange)
        if canonical_symbol is None:
            return None

        company_name = self._resolve_company_name(raw_quote, fallback=canonical_symbol)
        display_symbol = self._build_display_symbol(canonical_symbol, exchange)

        try:
            return StockSearchResult(
                symbol=canonical_symbol,
                company_name=company_name,
                exchange=exchange,
                display_symbol=display_symbol,
            )
        except ValueError:
            # StockSearchResult's own validation (e.g. an empty field
            # after normalization) rejected this entry -- treat as
            # malformed rather than propagating the domain entity's
            # ValueError out of this adapter.
            return None

    def _normalize_symbol(self, raw_symbol: str, exchange: StockExchange) -> str | None:
        """
        Strips the Yahoo exchange suffix (.NS or .BO) from `raw_symbol`
        and uppercases the result to produce a stable canonical symbol
        (e.g. "reliance.NS" -> "RELIANCE"), based on which suffix
        corresponds to `exchange`. Uppercasing here ensures canonical
        symbols are stable identifiers and that deduplication by
        (exchange, symbol) is case-insensitive.

        Returns None if the resulting canonical symbol is empty after
        stripping the suffix and surrounding whitespace.
        """
        suffix = next(
            (s for s, ex in _SUFFIX_TO_EXCHANGE.items() if ex == exchange), None
        )
        if suffix is None or not raw_symbol.upper().endswith(suffix):
            return None

        canonical = raw_symbol[: -len(suffix)].strip().upper()
        return canonical if canonical else None

    def _resolve_company_name(self, raw_quote: dict[str, Any], *, fallback: str) -> str:
        """
        Resolves a company name for a quote: prefers `longname` when it
        is a non-empty string, falls back to `shortname` when *that* is a
        non-empty string, and otherwise falls back to the canonical
        symbol.
        """
        long_name = raw_quote.get("longname")
        if isinstance(long_name, str) and long_name.strip():
            return long_name

        short_name = raw_quote.get("shortname")
        if isinstance(short_name, str) and short_name.strip():
            return short_name

        return fallback

    def _build_display_symbol(self, canonical_symbol: str, exchange: StockExchange) -> str:
        """
        Builds a stable, UI-facing display symbol of the form
        "<CANONICAL_SYMBOL>.<EXCHANGE>" (e.g. "RELIANCE.NSE",
        "500325.BSE"), independent of Yahoo's own suffix convention.
        """
        return f"{canonical_symbol}.{exchange.value}"