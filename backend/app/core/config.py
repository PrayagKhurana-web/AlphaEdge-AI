"""
Application-wide configuration for the AlphaEdge AI backend.

Settings are loaded via pydantic-settings' BaseSettings, which supports
environment-variable overrides out of the box -- every field below can be
set via a same-named (case-insensitive) environment variable, or via a
local .env file, or left at its default for local development. This is
the single source of configuration for the whole backend; per
PROJECT_CONTEXT.md, module-specific settings (like market_data's cache
TTL or stock_search's query limits) belong here rather than being
redefined ad hoc inside each module.
"""

from __future__ import annotations

import math

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central application settings, populated from environment variables
    (or a local .env file, if present) with sensible defaults for local
    development.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    market_data_request_timeout_seconds: float = Field(default=10.0)
    market_data_cache_ttl_seconds: int = Field(default=30)

    stock_search_request_timeout_seconds: float = Field(default=10.0)
    stock_search_max_query_length: int = Field(default=100)
    stock_search_default_limit: int = Field(default=8)
    stock_search_max_limit: int = Field(default=20)

    @field_validator("market_data_request_timeout_seconds")
    @classmethod
    def _validate_market_data_request_timeout_positive(cls, value: float) -> float:
        """
        Rejects a non-finite or non-positive market_data request timeout
        at settings load time. Finiteness is checked explicitly (not just
        positivity) since a float setting parsed from an environment
        variable could otherwise be "inf", "-inf", or "nan", none of
        which is a usable timeout value.
        """
        if not math.isfinite(value) or value <= 0:
            raise ValueError(
                "market_data_request_timeout_seconds must be finite and "
                f"strictly positive, got {value!r}"
            )
        return value

    @field_validator("market_data_cache_ttl_seconds")
    @classmethod
    def _validate_market_data_cache_ttl_positive(cls, value: int) -> int:
        """Rejects a non-positive market_data cache TTL at settings load time."""
        if value <= 0:
            raise ValueError(
                "market_data_cache_ttl_seconds must be strictly positive, "
                f"got {value!r}"
            )
        return value

    @field_validator("stock_search_request_timeout_seconds")
    @classmethod
    def _validate_stock_search_request_timeout_positive(cls, value: float) -> float:
        """
        Rejects a non-finite or non-positive stock_search request timeout
        at settings load time. Finiteness is checked explicitly (not just
        positivity) since a float setting parsed from an environment
        variable could otherwise be "inf", "-inf", or "nan", none of
        which is a usable timeout value.
        """
        if not math.isfinite(value) or value <= 0:
            raise ValueError(
                "stock_search_request_timeout_seconds must be finite and "
                f"strictly positive, got {value!r}"
            )
        return value

    @field_validator("stock_search_max_query_length")
    @classmethod
    def _validate_stock_search_max_query_length_positive(cls, value: int) -> int:
        """Rejects a non-positive max query length at settings load time."""
        if value <= 0:
            raise ValueError(
                "stock_search_max_query_length must be strictly positive, "
                f"got {value!r}"
            )
        return value

    @field_validator("stock_search_default_limit")
    @classmethod
    def _validate_stock_search_default_limit_positive(cls, value: int) -> int:
        """Rejects a non-positive default limit at settings load time."""
        if value <= 0:
            raise ValueError(
                "stock_search_default_limit must be strictly positive, "
                f"got {value!r}"
            )
        return value

    @field_validator("stock_search_max_limit")
    @classmethod
    def _validate_stock_search_max_limit_positive(cls, value: int) -> int:
        """Rejects a non-positive max limit at settings load time."""
        if value <= 0:
            raise ValueError(
                f"stock_search_max_limit must be strictly positive, got {value!r}"
            )
        return value

    @model_validator(mode="after")
    def _validate_stock_search_limit_relationship(self) -> "Settings":
        """
        Enforces stock_search_default_limit <= stock_search_max_limit.

        Implemented as a model-level validator (rather than a field
        validator on stock_search_max_limit reading from `info.data`) so
        this cross-field check does not depend on pydantic-settings'
        field declaration/validation order -- by the time an "after"
        model validator runs, every individual field validator has
        already succeeded, so both values are guaranteed present and
        individually valid here.
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
    Returns the process-wide Settings singleton, constructing (and
    validating) it on first call.

    Callers -- FastAPI dependency wiring, module-level composition code --
    should always call this rather than instantiating Settings() directly,
    so environment parsing and validation happen exactly once per process,
    not once per call site.
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings