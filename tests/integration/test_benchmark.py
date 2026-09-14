"""PostgreSQL integration tests for controlled before/after benchmarking."""

import os

import pytest
from sqlalchemy import text

from app.core.config import Settings
from app.db.connection import get_engine
from app.db.initialization import initialize_database
from app.optimizer.benchmark import BenchmarkError, BenchmarkMeasurement, BenchmarkService
from app.optimizer.explain import ExplainService
from app.optimizer.rules import OptimizationRuleEngine


pytestmark = pytest.mark.integration


def _require_postgres() -> None:
    if os.getenv("RUN_INTEGRATION_TESTS") != "1":
        pytest.skip("Set RUN_INTEGRATION_TESTS=1 to run PostgreSQL integration tests")


def _candidate_for_benchmark():
    query = "SELECT id, created_at FROM orders WHERE user_id = 4242"
    explanation = ExplainService().explain(query)
    candidates = OptimizationRuleEngine().recommend(explanation)
    return query, next(candidate for candidate in candidates if candidate.suggested_sql)


def test_benchmark_executes_and_cleans_up_controlled_index() -> None:
    _require_postgres()
    initialize_database(reset=True)
    query, candidate = _candidate_for_benchmark()
    settings = Settings(
        benchmark_timeout_ms=30000,
        benchmark_repetitions=2,
        benchmark_warmup_runs=0,
        benchmark_min_improvement_percent=5.0,
    )

    result = BenchmarkService(settings=settings).benchmark(
        query, candidate, repetitions=2, warmup_runs=0
    )

    assert result.original_query == query
    assert result.cleanup_completed is True
    assert len(result.baseline.execution_times_ms) == 2
    assert len(result.after.execution_times_ms) == 2
    assert result.baseline.node_type
    assert result.baseline.relation_name
    assert result.baseline.median_planning_time_ms is not None
    assert all(value >= 0 for value in result.baseline.execution_times_ms)
    assert all(value >= 0 for value in result.after.execution_times_ms)
    assert result.comparison.classification in {
        "improved",
        "regressed",
        "no_meaningful_change",
    }
    assert result.candidate_index_name not in _index_names("orders")
    assert "password" not in result.model_dump_json().lower()


def test_repeated_benchmark_runs_work_and_preserve_preexisting_equivalent_index() -> None:
    _require_postgres()
    initialize_database(reset=True)
    query, candidate = _candidate_for_benchmark()
    settings = Settings(benchmark_repetitions=1, benchmark_warmup_runs=0)
    service = BenchmarkService(settings=settings)

    first = service.benchmark(query, candidate, repetitions=1, warmup_runs=0)
    with get_engine().begin() as connection:
        connection.execute(text("CREATE INDEX preserved_orders_user_id ON orders(user_id)"))
    try:
        second = service.benchmark(query, candidate, repetitions=1, warmup_runs=0)
    finally:
        with get_engine().begin() as connection:
            connection.execute(text("DROP INDEX IF EXISTS preserved_orders_user_id"))

    assert first.cleanup_completed and second.cleanup_completed
    assert first.repetitions == second.repetitions == 1
    assert "preserved_orders_user_id" not in _index_names("orders")


def test_cleanup_occurs_when_after_measurement_fails(monkeypatch) -> None:
    _require_postgres()
    initialize_database(reset=True)
    query, candidate = _candidate_for_benchmark()
    service = BenchmarkService(settings=Settings(benchmark_repetitions=1, benchmark_warmup_runs=0))
    measurement = BenchmarkMeasurement(
        execution_times_ms=[1.0],
        median_execution_time_ms=1.0,
        mean_execution_time_ms=1.0,
        planning_times_ms=[0.1],
        median_planning_time_ms=0.1,
        node_type="Seq Scan",
        relation_name="orders",
    )
    calls = 0

    def fail_after(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise BenchmarkError("simulated after failure")
        return measurement

    monkeypatch.setattr(service, "_measure", fail_after)

    with pytest.raises(BenchmarkError, match="simulated after failure"):
        service.benchmark(query, candidate, repetitions=1, warmup_runs=0)

    assert not any(name.startswith("queryforge_benchmark_idx_") for name in _index_names("orders"))


def _index_names(table: str) -> set[str]:
    with get_engine().connect() as connection:
        return set(
            connection.execute(
                text(
                    "SELECT indexname FROM pg_indexes "
                    "WHERE schemaname = current_schema() AND tablename = :table_name"
                ),
                {"table_name": table},
            ).scalars()
        )