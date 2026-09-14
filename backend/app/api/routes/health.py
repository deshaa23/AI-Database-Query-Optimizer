"""Health check routes."""

from fastapi import APIRouter
from pydantic import BaseModel


router = APIRouter()


class HealthResponse(BaseModel):
    """Response returned by the application health check."""

    status: str


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Report whether the application process is running."""

    return HealthResponse(status="ok")
