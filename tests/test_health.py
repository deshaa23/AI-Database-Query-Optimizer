"""Tests for the health endpoint."""

from fastapi.testclient import TestClient

from app.api.routes import health as health_route
from app.main import app


client = TestClient(app)


def test_health_endpoint_returns_ok(monkeypatch) -> None:
    """The health endpoint reports application and database availability."""

    monkeypatch.setattr(health_route, "check_database_health", lambda: True)

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_health_endpoint_returns_degraded_when_database_is_unavailable(
    monkeypatch,
) -> None:
    """The health endpoint remains available when PostgreSQL is unavailable."""

    monkeypatch.setattr(health_route, "check_database_health", lambda: False)

    response = client.get("/api/v1/health")

    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "database": "unavailable"}
