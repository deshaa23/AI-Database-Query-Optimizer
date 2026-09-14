"""Health check routes."""

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.db.health import check_database_health


router = APIRouter()


class HealthResponse(BaseModel):
    """Response returned by the application health check."""

    status: str
    database: str


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse | JSONResponse:
    """Report application and PostgreSQL availability."""

    database_status = "ok" if check_database_health() else "unavailable"
    if database_status != "ok":
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "degraded", "database": database_status},
        )

    return HealthResponse(status="ok", database=database_status)
