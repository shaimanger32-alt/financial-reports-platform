"""Application factory and ASGI entry point."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import __version__
from api.config import get_api_settings
from api.routers import health

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


def create_app() -> FastAPI:
    """Build the ASGI application."""
    settings = get_api_settings()

    app = FastAPI(
        title="Financial Report Intelligence API",
        version=__version__,
        description="Deterministic analysis of public financial reports.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    return app


app = create_app()
