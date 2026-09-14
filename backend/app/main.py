"""FastAPI application entry point."""

from fastapi import FastAPI

from app.api.routes.analyze import router as analyze_router
from app.api.routes.health import router as health_router
from app.core.config import get_settings


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    settings = get_settings()
    application = FastAPI(title=settings.app_name)
    application.include_router(health_router, prefix="/api/v1")
    application.include_router(analyze_router, prefix="/api/v1")
    return application


app = create_app()
