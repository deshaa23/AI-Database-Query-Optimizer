"""Integration coverage for the benchmark-to-mock-AI pipeline."""

import os

import pytest

from app.ai.optimizer import AIOptimizer
from app.ai.provider import MockLLMProvider
from app.db.initialization import initialize_database
from app.optimizer.explain import ExplainService
from app.optimizer.rules import OptimizationRuleEngine


pytestmark = pytest.mark.integration


def test_benchmark_plan_flows_through_deterministic_and_mock_ai_layers() -> None:
    if os.getenv("RUN_INTEGRATION_TESTS") != "1":
        pytest.skip("Set RUN_INTEGRATION_TESTS=1 to run PostgreSQL integration tests")

    initialize_database()
    query = "SELECT id, created_at FROM orders WHERE user_id = 4242 ORDER BY created_at DESC"
    explain_result = ExplainService().explain(query)
    recommendations = OptimizationRuleEngine().recommend(explain_result)
    first = recommendations[0]
    provider = MockLLMProvider(
        {
            "summary": "The plan evidence was reviewed.",
            "primary_recommendation": first.title,
            "ranked_recommendations": [
                {
                    "recommendation_type": first.type,
                    "title": first.title,
                    "explanation": "Review the deterministic candidate using measured validation.",
                    "rationale": "This explanation is grounded in the supplied plan.",
                    "affected_table": first.affected_table,
                    "affected_columns": first.affected_columns,
                    "suggested_sql": first.suggested_sql,
                    "confidence": 0.7,
                }
            ],
            "tradeoffs": ["Validate write and storage tradeoffs."],
            "confidence": 0.7,
            "validation_steps": ["Compare EXPLAIN ANALYZE before and after validation."],
        }
    )

    analysis = AIOptimizer(provider).analyze(
        query=query,
        explain_result=explain_result,
        recommendations=recommendations,
    )

    assert analysis.ranked_recommendations[0].affected_table == first.affected_table