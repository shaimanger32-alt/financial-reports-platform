"""Health endpoint.

Phase 0 exit criterion: the API can perform a database health check and the web
app can consume it (spec section 39).
"""

import logging

from fastapi import APIRouter, Response, status

from api import __version__
from api.config import get_api_settings
from api.schemas import HealthResponse
from database import check_connection

logger = logging.getLogger(__name__)

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
def health(response: Response) -> HealthResponse:
    """Report service and database reachability.

    Returns 503 when a dependency is down so that orchestrators and the web app
    can distinguish 'reachable but degraded' from 'healthy'.
    """
    settings = get_api_settings()

    try:
        check_connection()
    except Exception as exc:
        logger.warning("database health check failed", exc_info=exc)
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthResponse(
            status="degraded",
            database="error",
            version=__version__,
            environment=settings.environment,
            detail=type(exc).__name__,
        )

    return HealthResponse(
        status="ok",
        database="ok",
        version=__version__,
        environment=settings.environment,
    )
