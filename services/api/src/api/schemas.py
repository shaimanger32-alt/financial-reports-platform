"""Response models. These define the public API contract consumed by web and mobile."""

from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Liveness and dependency status of the service."""

    status: Literal["ok", "degraded"] = Field(
        description="'ok' only when every dependency is reachable.",
    )
    database: Literal["ok", "error"] = Field(
        description="Result of a SELECT 1 against the canonical store.",
    )
    version: str = Field(description="Service version.")
    environment: str = Field(description="Deployment environment name.")
    detail: str | None = Field(
        default=None,
        description="Failure reason when status is 'degraded'.",
    )
