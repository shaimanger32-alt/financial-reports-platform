"""Database configuration, sourced from the environment only.

Secrets never live in code or in the repository (spec section 35).
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """Connection settings for the canonical PostgreSQL store."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(
        description="SQLAlchemy URL, e.g. postgresql+psycopg://user:pass@host:5432/db",
    )
    sql_echo: bool = Field(
        default=False,
        description="Log every emitted statement. Debugging only.",
    )


@lru_cache(maxsize=1)
def get_database_settings() -> DatabaseSettings:
    """Return process-wide database settings."""
    return DatabaseSettings()  # type: ignore[call-arg]  # values come from the environment
