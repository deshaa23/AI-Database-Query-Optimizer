"""PostgreSQL-backed API integration coverage."""

import os

import pytest
from fastapi.testclient import TestClient

from app.api.routes import analyze as analyze_route
from app.db.initialization import initialize_database
from app.main import app
from app.services.analysis import AnalysisService


pytestmark = pytest.mark.integration


def test_analyze_endpoint_returns_plan_and_recommendations() -> None:
    if os.getenv("RUN_INTEGRATION_TESTS") != "1":
        pytest.skip("Set RUN_INTEGRATION_TESTS=1 to run PostgreSQL integration tests")

    initialize_database()
    app.dependency_overrides[analyze_route.get_analysis_service] = lambda: AnalysisService()
    try:
        response = TestClient(app).post(
            "/api/v1/analyze",
            json={
                "query": "SELECT id, created_at FROM orders WHERE user_id = 4242",
                "include_ai": False,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["execution_plan"]["plan"]["node_type"]
    assert isinstance(body["deterministic_recommendations"], list)