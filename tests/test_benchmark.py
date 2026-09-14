"""Unit tests for controlled benchmark calculations and candidate validation."""

import pytest
from sqlalchemy import create_engine, text

from app.optimizer.benchmark import (
    BenchmarkMeasurement,
    BenchmarkResult,
    CandidateValidationError,
    _benchmark_index_name,
    _deterministic_candidate_sql,
    calculate_improvement_percent,
    calculate_mean,
    calculate_median,
    classify_improvement,
    validate_candidate,
)
from app.optimizer.models import OptimizationRecommendation


def _candidate(
    *,
    table: str = "orders",
    columns: list[str] | None = None,
    candidate_type: str = "MISSING_INDEX_CANDIDATE",
) -> OptimizationRecommendation:
    columns = columns or ["user_id"]
    return OptimizationRecommendation(
        type=candidate_type,
        severity="medium",
        title="candidate",
        description="candidate",
        rationale="candidate",
        affected_table=table,
        affected_columns=columns,
        suggested_sql=_deterministic_candidate_sql(table, columns),
        confidence=0.8,
    )


def test_mean_and_median_calculation() -> None:
    assert calculate_mean([1.0, 2.0, 9.0]) == 4.0
    assert calculate_median([1.0, 2.0, 9.0]) == 2.0
    assert calculate_median([1.0, 9.0]) == 5.0


def test_improvement_and_regression_calculation() -> None:
    assert calculate_improvement_percent(100.0, 70.0) == 30.0
    assert calculate_improvement_percent(100.0, 130.0) == -30.0
    assert calculate_improvement_percent(0.0, 10.0) is None
    assert calculate_improvement_percent(None, 10.0) is None


@pytest.mark.parametrize(
    ("improvement", "expected"),
    [
        (5.0, "improved"),
        (-5.0, "regressed"),
        (4.99, "no_meaningful_change"),
        (-4.99, "no_meaningful_change"),
        (None, "no_meaningful_change"),
    ],
)
def test_threshold_classification(improvement: float | None, expected: str) -> None:
    assert classify_improvement(improvement, 5.0) == expected


def test_candidate_index_name_is_deterministic_and_bounded() -> None:
    first = _benchmark_index_name("orders", ["user_id"])
    second = _benchmark_index_name("orders", ["user_id"])
    long_name = _benchmark_index_name("orders", ["column_" + "x" * 100])

    assert first == second
    assert first.startswith("queryforge_benchmark_idx_")
    assert len(long_name) <= 63


def test_candidate_sql_is_deterministic() -> None:
    assert _deterministic_candidate_sql("orders", ["user_id"]) == (
        "CREATE INDEX idx_orders_user_id ON orders(user_id);"
    )


def test_nullable_metrics_and_result_model_validation() -> None:
    measurement = BenchmarkMeasurement(
        execution_times_ms=[1.0],
        median_execution_time_ms=1.0,
        mean_execution_time_ms=1.0,
        planning_times_ms=[0.1],
        median_planning_time_ms=0.1,
    )
    result = BenchmarkResult(
        original_query="SELECT 1",
        candidate_type="MISSING_INDEX_CANDIDATE",
        candidate_table="orders",
        candidate_columns=["user_id"],
        candidate_index_name="queryforge_benchmark_idx_orders_user_id",
        repetitions=1,
        warmup_runs=0,
        baseline=measurement,
        after=measurement,
        comparison={
            "baseline_median_execution_time_ms": 1.0,
            "after_median_execution_time_ms": 1.0,
            "execution_time_delta_ms": 0.0,
            "improvement_percent": 0.0,
            "classification": "no_meaningful_change",
            "scan_type_changed": False,
        },
        cleanup_completed=True,
    )

    assert result.baseline.index_name is None
    assert result.after.shared_read_blocks is None


def test_invalid_table_and_column_are_rejected_without_postgres() -> None:
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE orders (user_id INTEGER NOT NULL)"))

    with engine.connect() as connection:
        with pytest.raises(CandidateValidationError, match="Invalid candidate table"):
            validate_candidate(connection, _candidate(table="orders; DROP TABLE users"))
        with pytest.raises(CandidateValidationError, match="do not exist"):
            validate_candidate(connection, _candidate(columns=["missing_column"]))


def test_unsupported_recommendation_is_rejected() -> None:
    candidate = _candidate().model_construct(type="PERFORMANCE_BOTTLENECK")
    engine = create_engine("sqlite://")

    with engine.connect() as connection:
        with pytest.raises(CandidateValidationError, match="Unsupported candidate type"):
            validate_candidate(connection, candidate)