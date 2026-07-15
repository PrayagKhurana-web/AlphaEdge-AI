"""
Application-wide configuration for the AlphaEdge AI backend.

Settings are loaded via pydantic-settings' BaseSettings, which supports
environment-variable overrides out of the box -- every field below can be
set via a same-named (case-insensitive) environment variable, or via a
local .env file, or left at its default for local development. This is
the single source of configuration for the whole backend; per
PROJECT_CONTEXT.md, module-specific settings (like market_data's cache
TTL) belong here rather than being redefined ad hoc inside each module.
"""

from __future__ import annotations

from pydantic import Field, field_validator
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

    @field_validator("market_data_request_timeout_seconds")
    @classmethod
    def _validate_request_timeout_positive(cls, value: float) -> float:
        """Rejects a non-positive request timeout at settings load time."""
        if value <= 0:
            raise ValueError(
                "market_data_request_timeout_seconds must be strictly "
                f"positive, got {value!r}"
            )
        return value

    @field_validator("market_data_cache_ttl_seconds")
    @classmethod
    def _validate_cache_ttl_positive(cls, value: int) -> int:
        """Rejects a non-positive cache TTL at settings load time."""
        if value <= 0:
            raise ValueError(
                "market_data_cache_ttl_seconds must be strictly positive, "
                f"got {value!r}"
            )
        return value


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