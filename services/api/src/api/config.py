"""API configuration, sourced from the environment only."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ApiSettings(BaseSettings):
    """Runtime settings for the FastAPI service."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = Field(default="development")
    cors_allow_origins: str = Field(
        default="http://localhost:3000",
        description=(
            "Comma-separated origins permitted to call the API from a browser. "
            "A plain string rather than a list, because JSON-in-environment-variable "
            "is a reliable source of deployment breakage."
        ),
    )

    @property
    def cors_origins(self) -> list[str]:
        """Parsed origin list, empty entries discarded."""
        return [origin.strip() for origin in self.cors_allow_origins.split(",") if origin.strip()]


@lru_cache(maxsize=1)
def get_api_settings() -> ApiSettings:
    """Return process-wide API settings."""
    return ApiSettings()
