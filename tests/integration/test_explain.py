"""Integration coverage for real PostgreSQL execution plans."""

import os

import pytest

from app.db.initialization import initialize_database
from app.optimizer.explain import ExplainService


pytestmark = pytest.mark.integration


def test_explain_returns_a_real_benchmark_plan() -> None:
    if os.getenv("RUN_INTEGRATION_TESTS") != "1":
        pytest.skip("Set RUN_INTEGRATION_TESTS=1 to run PostgreSQL integration tests")

    initialize_database()
    result = ExplainService().explain("SELECT id, created_at FROM orders WHERE user_id = 4242")

    assert result.plan.node_type
    assert result.execution_time_ms is not None
    assert result.execution_time_ms >= 0