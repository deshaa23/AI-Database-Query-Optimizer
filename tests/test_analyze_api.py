"""API tests for the QueryForge analysis endpoint."""

from fastapi.testclient import TestClient

from app.ai.optimizer import AIOptimizer
from app.ai.provider import MockLLMProvider
from app.api.routes import analyze as analyze_route
from app.main import app
from app.optimizer.benchmark import BenchmarkError
from app.optimizer.explain import validate_select_query
from app.optimizer.models import ExplainResult, OptimizationRecommendation, PlanNode, PlanObservation
from app.services.analysis import AnalysisError, AnalysisService, AIAnalysisError


def _explain_result() -> ExplainResult:
    return ExplainResult(
        query="SELECT id FROM orders WHERE user_id = 4242",
        execution_time_ms=2.5,
        planning_time_ms=0.2,
        plan=PlanNode(
            node_type="Seq Scan",
            relation="orders",
            filter="user_id = 4242",
            planned_rows=10,
            actual_rows=10,
            actual_loops=1,
        ),
        observations=[
            PlanObservation(
                type="sequential_scan",
                severity="medium",
                message="Sequential scan detected.",
                node_type="Seq Scan",
                relation="orders",
            )
        ],
    )


def _recommendation() -> OptimizationRecommendation:
    return OptimizationRecommendation(
        type="MISSING_INDEX_CANDIDATE",
        severity="medium",
        title="Filtered scan candidate",
        description="A candidate was found.",
        rationale="The filter is selective enough to inspect.",
        evidence=["Filter: user_id = 4242"],
        affected_table="orders",
        affected_columns=["user_id"],
        suggested_sql="CREATE INDEX idx_orders_user_id ON orders(user_id);",
        confidence=0.8,
    )


class FakeExplainService:
    def explain(self, query: str) -> ExplainResult:
        safe_query = validate_select_query(query)
        return _explain_result().model_copy(update={"query": safe_query})


class FakeRuleEngine:
    def recommend(self, explain_result: ExplainResult) -> list[OptimizationRecommendation]:
        return [_recommendation()]


class FakeBenchmarkService:
    def __init__(self) -> None:
        self.calls = 0

    def benchmark(self, query: str, candidate: OptimizationRecommendation):
        self.calls += 1
        return None


def _service(
    *,
    include_ai: bool = False,
    benchmark_service: FakeBenchmarkService | None = None,
) -> AnalysisService:
    ai_optimizer = None
    if include_ai:
        candidate = _recommendation()
        response = {
            "summary": "Grounded analysis.",
            "primary_recommendation": candidate.title,
            "ranked_recommendations": [
                {
                    "recommendation_type": candidate.type,
                    "title": candidate.title,
                    "explanation": "Review the candidate.",
                    "rationale": "It is grounded in the plan.",
                    "affected_table": candidate.affected_table,
                    "affected_columns": candidate.affected_columns,
                    "suggested_sql": candidate.suggested_sql,
                    "confidence": 0.7,
                }
            ],
            "tradeoffs": ["Validate maintenance cost."],
            "confidence": 0.7,
            "validation_steps": ["Run EXPLAIN ANALYZE before and after."],
        }
        ai_optimizer = AIOptimizer(MockLLMProvider(response))
    return AnalysisService(
        explain_service=FakeExplainService(),
        rule_engine=FakeRuleEngine(),
        ai_optimizer=ai_optimizer,
        benchmark_service=benchmark_service or FakeBenchmarkService(),
    )


def _client(service: AnalysisService) -> TestClient:
    app.dependency_overrides[analyze_route.get_analysis_service] = lambda: service
    return TestClient(app)


def teardown_function() -> None:
    app.dependency_overrides.clear()


def test_successful_select_analysis_is_structured_and_serializable() -> None:
    response = _client(_service()).post(
        "/api/v1/analyze",
        json={"query": "SELECT id FROM orders WHERE user_id = 4242", "include_ai": False},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["query"].startswith("SELECT")
    assert body["execution_plan"]["plan"]["node_type"] == "Seq Scan"
    assert body["observations"]
    assert body["deterministic_recommendations"][0]["type"] == "MISSING_INDEX_CANDIDATE"
    assert body["ai_analysis"] is None
    assert body["benchmark"] is None


def test_invalid_queries_return_400() -> None:
    client = _client(_service())
    for query in ["UPDATE users SET name = 'x'", "SELECT 1; SELECT 2"]:
        response = client.post("/api/v1/analyze", json={"query": query, "include_ai": False})
        assert response.status_code == 400


def test_empty_query_and_unknown_fields_are_rejected() -> None:
    client = _client(_service())
    assert client.post("/api/v1/analyze", json={"query": ""}).status_code == 422
    assert client.post(
        "/api/v1/analyze", json={"query": "SELECT 1", "credentials": "secret"}
    ).status_code == 422


def test_trailing_semicolon_is_accepted() -> None:
    response = _client(_service()).post(
        "/api/v1/analyze",
        json={"query": "SELECT id FROM orders;", "include_ai": False},
    )
    assert response.status_code == 200


def test_ai_is_used_only_when_requested() -> None:
    no_ai_response = _client(_service(include_ai=False)).post(
        "/api/v1/analyze", json={"query": "SELECT 1", "include_ai": False}
    )
    ai_response = _client(_service(include_ai=True)).post(
        "/api/v1/analyze", json={"query": "SELECT 1", "include_ai": True}
    )

    assert no_ai_response.json()["ai_analysis"] is None
    assert ai_response.status_code == 200
    assert ai_response.json()["ai_analysis"]["summary"] == "Grounded analysis."


def test_benchmark_is_opt_in_and_called_only_when_requested() -> None:
    benchmark_service = FakeBenchmarkService()
    service = _service(benchmark_service=benchmark_service)
    client = _client(service)

    client.post("/api/v1/analyze", json={"query": "SELECT 1", "include_ai": False})
    assert benchmark_service.calls == 0
    client.post(
        "/api/v1/analyze",
        json={"query": "SELECT 1", "include_ai": False, "include_benchmark": True},
    )
    assert benchmark_service.calls == 1


def test_health_endpoint_still_works() -> None:
    response = _client(_service()).get("/api/v1/health")
    assert response.status_code in {200, 503}


def test_database_and_ai_failures_are_controlled() -> None:
    class FailingService:
        def analyze(self, **kwargs):
            raise AnalysisError("internal database details")

    response = _client(FailingService()).post(
        "/api/v1/analyze", json={"query": "SELECT 1", "include_ai": False}
    )
    assert response.status_code == 500
    assert "internal database details" not in response.text

    class FailingAIService:
        def analyze(self, **kwargs):
            raise AIAnalysisError("provider secret")

    response = _client(FailingAIService()).post(
        "/api/v1/analyze", json={"query": "SELECT 1"}
    )
    assert response.status_code == 503
    assert "provider secret" not in response.text
