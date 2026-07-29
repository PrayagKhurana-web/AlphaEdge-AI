"""
Application-wide configuration for the AlphaEdge AI backend.

Settings are loaded via pydantic-settings' BaseSettings, which supports
environment-variable overrides out of the box -- every field below can be
set via a same-named (case-insensitive) environment variable, or via a
local .env file, or left at its default for local development. This is
the single source of configuration for the whole backend; per
PROJECT_CONTEXT.md, module-specific settings (like market_data's cache
TTL, stock_search's query limits, stock_details' request timeout,
stock_history's request timeout, or company_fundamentals' request
timeout) belong here rather than being redefined ad hoc inside each
module.

This file must remain independent of feature modules -- it never imports
from market_data, stock_search, stock_details, stock_history, or any
other module under app/modules/.
"""

from __future__ import annotations

import math

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _validate_finite_positive_timeout(value: float, *, field_name: str) -> float:
    """
    Shared validation logic for every "request timeout in seconds"
    setting in this class: rejects non-finite values (NaN, positive
    infinity, negative infinity) and non-positive values (zero or
    negative).

    Factored out as a single helper so market_data_request_timeout_seconds,
    stock_search_request_timeout_seconds,
    stock_details_request_timeout_seconds,
    stock_history_request_timeout_seconds, and
    company_fundamentals_request_timeout_seconds all enforce identical
    rules without duplicating the same finiteness/positivity check.
    """
    if not math.isfinite(value) or value <= 0:
        raise ValueError(
            f"{field_name} must be finite and strictly positive, got {value!r}"
        )
    return value


class Settings(BaseSettings):
    """
    Central application settings, populated from environment variables
    (or a local .env file, if present) with sensible defaults for local
    development.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/alphaedge"
    )

    market_data_request_timeout_seconds: float = Field(default=10.0)
    market_data_cache_ttl_seconds: int = Field(default=30)

    stock_search_request_timeout_seconds: float = Field(default=10.0)
    stock_search_max_query_length: int = Field(default=100)
    stock_search_default_limit: int = Field(default=8)
    stock_search_max_limit: int = Field(default=20)

    stock_details_request_timeout_seconds: float = Field(default=10.0)

    stock_history_request_timeout_seconds: float = Field(default=10.0)

    company_fundamentals_request_timeout_seconds: float = Field(default=10.0)

    financial_statements_request_timeout_seconds: float = Field(default=15.0)

    @field_validator("market_data_request_timeout_seconds")
    @classmethod
    def _validate_market_data_request_timeout_positive(cls, value: float) -> float:
        """Reject a non-finite or non-positive market-data timeout."""
        return _validate_finite_positive_timeout(
            value,
            field_name="market_data_request_timeout_seconds",
        )

    @field_validator("market_data_cache_ttl_seconds")
    @classmethod
    def _validate_market_data_cache_ttl_positive(cls, value: int) -> int:
        """Reject a non-positive market-data cache TTL."""
        if value <= 0:
            raise ValueError(
                "market_data_cache_ttl_seconds must be strictly positive, "
                f"got {value!r}"
            )
        return value

    @field_validator("stock_search_request_timeout_seconds")
    @classmethod
    def _validate_stock_search_request_timeout_positive(
        cls,
        value: float,
    ) -> float:
        """Reject a non-finite or non-positive stock-search timeout."""
        return _validate_finite_positive_timeout(
            value,
            field_name="stock_search_request_timeout_seconds",
        )

    @field_validator("stock_search_max_query_length")
    @classmethod
    def _validate_stock_search_max_query_length_positive(
        cls,
        value: int,
    ) -> int:
        """Reject a non-positive maximum query length."""
        if value <= 0:
            raise ValueError(
                "stock_search_max_query_length must be strictly positive, "
                f"got {value!r}"
            )
        return value

    @field_validator("stock_search_default_limit")
    @classmethod
    def _validate_stock_search_default_limit_positive(
        cls,
        value: int,
    ) -> int:
        """Reject a non-positive default result limit."""
        if value <= 0:
            raise ValueError(
                "stock_search_default_limit must be strictly positive, "
                f"got {value!r}"
            )
        return value

    @field_validator("stock_search_max_limit")
    @classmethod
    def _validate_stock_search_max_limit_positive(
        cls,
        value: int,
    ) -> int:
        """Reject a non-positive maximum result limit."""
        if value <= 0:
            raise ValueError(
                f"stock_search_max_limit must be strictly positive, got {value!r}"
            )
        return value

    @field_validator("stock_details_request_timeout_seconds")
    @classmethod
    def _validate_stock_details_request_timeout_positive(
        cls,
        value: float,
    ) -> float:
        """Reject a non-finite or non-positive stock-details timeout."""
        return _validate_finite_positive_timeout(
            value,
            field_name="stock_details_request_timeout_seconds",
        )

    @field_validator("stock_history_request_timeout_seconds")
    @classmethod
    def _validate_stock_history_request_timeout_positive(
        cls,
        value: float,
    ) -> float:
        """Reject a non-finite or non-positive stock-history timeout."""
        return _validate_finite_positive_timeout(
            value,
            field_name="stock_history_request_timeout_seconds",
        )

    @field_validator("company_fundamentals_request_timeout_seconds")
    @classmethod
    def _validate_company_fundamentals_request_timeout_positive(
        cls,
        value: float,
    ) -> float:
        """Reject a non-finite or non-positive company-fundamentals timeout."""
        return _validate_finite_positive_timeout(
            value,
            field_name="company_fundamentals_request_timeout_seconds",
        )


    @field_validator("financial_statements_request_timeout_seconds")
    @classmethod
    def _validate_financial_statements_request_timeout_positive(
        cls,
        value: float,
    ) -> float:
        """Reject a non-finite or non-positive financial-statements timeout."""
        return _validate_finite_positive_timeout(
            value,
            field_name="financial_statements_request_timeout_seconds",
        )
    @model_validator(mode="after")
    def _validate_stock_search_limit_relationship(self) -> "Settings":
        """
        Enforce stock_search_default_limit <= stock_search_max_limit.

        Implemented as a model-level validator so the cross-field check
        runs only after both fields have passed their individual
        validation.
        """
        if self.stock_search_default_limit > self.stock_search_max_limit:
            raise ValueError(
                "stock_search_default_limit "
                f"({self.stock_search_default_limit}) must not exceed "
                f"stock_search_max_limit ({self.stock_search_max_limit})"
            )
        return self


_settings: Settings | None = None


def get_settings() -> Settings:
    """
    Return the process-wide Settings singleton, constructing and
    validating it on first use.
    """
    global _settings

    if _settings is None:
        _settings = Settings()

    return _settings
