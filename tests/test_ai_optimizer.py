"""Unit tests for grounded AI optimization reasoning."""

import pytest

from app.ai.optimizer import AIOptimizer
from app.ai.provider import AIConfigurationError, AIValidationError, MockLLMProvider, OpenAIProvider
from app.core.config import Settings
from app.optimizer.models import ExplainResult, OptimizationRecommendation, PlanNode


def _candidate(sql: str | None = "CREATE INDEX idx_orders_user_id ON orders(user_id);"):
    return OptimizationRecommendation(
        type="MISSING_INDEX_CANDIDATE",
        severity="medium",
        title="Filtered scan",
        description="A filtered sequential scan was observed.",
        rationale="A simple equality filter identifies a candidate.",
        evidence=["Filter: user_id = 4242"],
        affected_table="orders",
        affected_columns=["user_id"],
        suggested_sql=sql,
        confidence=0.8,
    )


def _result() -> ExplainResult:
    return ExplainResult(
        query="SELECT id FROM orders WHERE user_id = 4242",
        execution_time_ms=12.5,
        planning_time_ms=0.4,
        plan=PlanNode(
            node_type="Seq Scan",
            relation="orders",
            filter="user_id = 4242",
            actual_total_time=12.0,
            actual_rows=20,
            actual_loops=1,
        ),
    )


def _response(candidate: OptimizationRecommendation, suggested_sql: str | None = None) -> dict:
    return {
        "summary": "The plan contains a filtered sequential scan.",
        "primary_recommendation": "Consider the deterministic index candidate after validation.",
        "ranked_recommendations": [
            {
                "recommendation_type": candidate.type,
                "title": "Validate the filtered scan candidate",
                "explanation": "The candidate may reduce work for this equality filter.",
                "rationale": "This is grounded in the supplied sequential scan evidence.",
                "affected_table": candidate.affected_table,
                "affected_columns": candidate.affected_columns,
                "suggested_sql": suggested_sql,
                "confidence": 0.75,
            }
        ],
        "tradeoffs": ["Consider write overhead and index maintenance."],
        "confidence": 0.75,
        "validation_steps": ["Run EXPLAIN ANALYZE before and after human-approved changes."],
    }


def test_valid_structured_output_produces_analysis() -> None:
    candidate = _candidate()
    provider = MockLLMProvider(_response(candidate, candidate.suggested_sql))

    analysis = AIOptimizer(provider).analyze(
        query=_result().query,
        explain_result=_result(),
        recommendations=[candidate],
    )

    assert analysis.ranked_recommendations[0].suggested_sql == candidate.suggested_sql
    assert 0.0 <= analysis.confidence <= 1.0


def test_malformed_output_is_rejected() -> None:
    provider = MockLLMProvider("{not-json")

    with pytest.raises(AIValidationError, match="valid OptimizationAnalysis"):
        AIOptimizer(provider).analyze(
            query=_result().query,
            explain_result=_result(),
            recommendations=[_candidate()],
        )


def test_deterministic_sql_is_preserved_exactly() -> None:
    candidate = _candidate()
    provider = MockLLMProvider(_response(candidate, "CREATE INDEX changed ON orders(user_id);"))

    with pytest.raises(AIValidationError, match="exactly match"):
        AIOptimizer(provider).analyze(
            query=_result().query,
            explain_result=_result(),
            recommendations=[candidate],
        )


def test_no_deterministic_sql_cannot_gain_executable_sql() -> None:
    candidate = _candidate(sql=None)
    provider = MockLLMProvider(_response(candidate, "CREATE INDEX invented ON orders(user_id);"))

    with pytest.raises(AIValidationError, match="exactly match"):
        AIOptimizer(provider).analyze(
            query=_result().query,
            explain_result=_result(),
            recommendations=[candidate],
        )


def test_confidence_bounds_are_validated() -> None:
    candidate = _candidate()
    response = _response(candidate, candidate.suggested_sql)
    response["confidence"] = 1.1
    provider = MockLLMProvider(response)

    with pytest.raises(AIValidationError):
        AIOptimizer(provider).analyze(
            query=_result().query,
            explain_result=_result(),
            recommendations=[candidate],
        )


def test_mock_provider_is_offline_and_prompt_contains_evidence() -> None:
    candidate = _candidate()
    provider = MockLLMProvider(_response(candidate, candidate.suggested_sql))

    AIOptimizer(provider).analyze(
        query=_result().query,
        explain_result=_result(),
        recommendations=[candidate],
    )

    assert len(provider.prompts) == 1
    prompt = provider.prompts[0]
    assert _result().query in prompt
    assert "12.5" in prompt
    assert "Seq Scan" in prompt
    assert "orders" in prompt
    assert "user_id = 4242" in prompt
    assert candidate.suggested_sql in prompt


def test_missing_configuration_raises_clear_error() -> None:
    with pytest.raises(AIConfigurationError, match="AI_PROVIDER"):
        OpenAIProvider(Settings(ai_provider="", ai_model="", openai_api_key=""))


def test_invalid_recommendation_evidence_is_rejected() -> None:
    candidate = _candidate()
    response = _response(candidate, candidate.suggested_sql)
    response["ranked_recommendations"][0]["affected_table"] = "users"
    provider = MockLLMProvider(response)

    with pytest.raises(AIValidationError, match="deterministic optimizer evidence"):
        AIOptimizer(provider).analyze(
            query=_result().query,
            explain_result=_result(),
            recommendations=[candidate],
        )
