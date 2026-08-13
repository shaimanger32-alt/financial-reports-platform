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

    sec_edgar_api_base_url: str = Field(
        default="https://data.sec.gov/api/xbrl",
        description="SEC EDGAR structured data root. Configuration, never a constant in code.",
    )
    sec_edgar_files_base_url: str = Field(
        default="https://www.sec.gov/files",
        description="Where SEC publishes its static reference files, such as the ticker index.",
    )
    sec_edgar_user_agent: str = Field(
        default="",
        description=(
            "SEC requires a User-Agent naming the caller and a contact address. "
            "Requests without one are refused. There is no API key; this is the "
            "whole of the access requirement."
        ),
    )
    sec_edgar_request_timeout_seconds: float = Field(default=60.0)
    sec_edgar_min_request_interval_seconds: float = Field(
        default=0.11,
        description="SEC asks for no more than 10 requests a second. This paces them.",
    )

    raw_archive_dir: str = Field(
        default="data/raw",
        description="Root for archived provider payloads. Git-ignored.",
    )


@lru_cache(maxsize=1)
def get_ingestion_settings() -> IngestionSettings:
    """Return process-wide ingestion settings."""
    return IngestionSettings()
