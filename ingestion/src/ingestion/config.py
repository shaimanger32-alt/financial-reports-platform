"""Ingestion configuration, sourced from the environment only."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class IngestionSettings(BaseSettings):
    """Provider endpoints and archive location."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    magna_api_base_url: str = Field(
        default="https://xbrl.magna.isa.gov.il/api",
        description="MAGNA XBRL query API root. Configuration, never a constant in code.",
    )
    magna_results_base_url: str = Field(
        default="https://xbrl.magna.isa.gov.il/public/search",
        description="Where completed MAGNA result files are published.",
    )
    magna_request_timeout_seconds: float = Field(default=60.0)
    magna_poll_attempts: int = Field(
        default=20,
        description="How many times to poll for a result file before giving up.",
    )
    magna_poll_initial_delay_seconds: float = Field(default=2.0)
    magna_poll_max_delay_seconds: float = Field(default=15.0)

    raw_archive_dir: str = Field(
        default="data/raw",
        description="Root for archived provider payloads. Git-ignored.",
    )


@lru_cache(maxsize=1)
def get_ingestion_settings() -> IngestionSettings:
    """Return process-wide ingestion settings."""
    return IngestionSettings()
