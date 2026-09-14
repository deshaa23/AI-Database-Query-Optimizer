"""Controlled before/after PostgreSQL performance benchmarking."""

import hashlib
import re
from collections.abc import Iterator
from statistics import mean, median
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import Engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import Settings, get_settings
from app.db.connection import get_engine
from app.optimizer.explain import ExplainService, validate_select_query
from app.optimizer.models import ExplainResult, OptimizationRecommendation, PlanNode


_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SUPPORTED_CANDIDATE = "MISSING_INDEX_CANDIDATE"
_BENCHMARK_INDEX_PREFIX = "queryforge_benchmark_idx_"


class BenchmarkError(RuntimeError):
    """Raised when a controlled benchmark cannot complete safely."""


class CandidateValidationError(BenchmarkError):
    """Raised when a recommendation is not a supported deterministic candidate."""


class BenchmarkMeasurement(BaseModel):
    """Repeated EXPLAIN ANALYZE measurements for one benchmark phase."""

    execution_times_ms: list[float]
    median_execution_time_ms: float | None
    mean_execution_time_ms: float | None
    planning_times_ms: list[float]
    median_planning_time_ms: float | None
    node_type: str | None = None
    relation_name: str | None = None
    index_name: str | None = None
    actual_rows: float | None = None
    planned_rows: float | None = None
    shared_hit_blocks: int | None = None
    shared_read_blocks: int | None = None


class BenchmarkComparison(BaseModel):
    """Comparison of baseline and after median execution times."""

    baseline_median_execution_time_ms: float | None
    after_median_execution_time_ms: float | None
    execution_time_delta_ms: float | None
    improvement_percent: float | None
    classification: Literal["improved", "regressed", "no_meaningful_change"]
    scan_type_changed: bool


class BenchmarkResult(BaseModel):
    """Auditable result of one controlled candidate benchmark."""

    original_query: str
    candidate_type: str
    candidate_table: str
    candidate_columns: list[str]
    candidate_index_name: str
    repetitions: int
    warmup_runs: int
    baseline: BenchmarkMeasurement
    after: BenchmarkMeasurement
    comparison: BenchmarkComparison
    cleanup_completed: bool


def calculate_mean(values: list[float]) -> float | None:
    """Return the arithmetic mean, or None when no measurements exist."""

    return mean(values) if values else None


def calculate_median(values: list[float]) -> float | None:
    """Return the median, or None when no measurements exist."""

    return median(values) if values else None


def calculate_improvement_percent(
    baseline_median_ms: float | None,
    after_median_ms: float | None,
) -> float | None:
    """Calculate improvement without reporting a misleading zero-baseline percentage."""

    if (
        baseline_median_ms is None
        or after_median_ms is None
        or baseline_median_ms <= 0
        or after_median_ms < 0
    ):
        return None
    return ((baseline_median_ms - after_median_ms) / baseline_median_ms) * 100


def classify_improvement(
    improvement_percent: float | None,
    threshold_percent: float,
) -> Literal["improved", "regressed", "no_meaningful_change"]:
    """Classify one comparison using the configured threshold."""

    if improvement_percent is None:
        return "no_meaningful_change"
    if improvement_percent >= threshold_percent:
        return "improved"
    if improvement_percent <= -threshold_percent:
        return "regressed"
    return "no_meaningful_change"


def _walk(node: PlanNode) -> Iterator[PlanNode]:
    yield node
    for child in node.plans:
        yield from _walk(child)


def _measurement_node(result: ExplainResult) -> PlanNode:
    """Prefer a scan node for comparison, otherwise use the plan root."""

    for node in _walk(result.plan):
        if node.node_type in {"Seq Scan", "Index Scan", "Index Only Scan", "Bitmap Heap Scan"}:
            return node
    return result.plan


def _benchmark_index_name(table: str, columns: list[str]) -> str:
    """Build a deterministic PostgreSQL-safe name within the 63-byte limit."""

    readable = _BENCHMARK_INDEX_PREFIX + table + "_" + "_".join(columns)
    if len(readable) <= 55:
        return readable
    digest = hashlib.sha256(readable.encode("utf-8")).hexdigest()[:10]
    return readable[: 63 - len(digest) - 1] + "_" + digest


def _deterministic_candidate_sql(table: str, columns: list[str]) -> str:
    """Return the exact SQL emitted by the deterministic recommendation engine."""

    return f"CREATE INDEX idx_{table}_{'_'.join(columns)} ON {table}({', '.join(columns)});"


def _validate_identifier(value: str, label: str) -> None:
    if not _IDENTIFIER.fullmatch(value):
        raise CandidateValidationError(f"Invalid {label}: {value!r}")


def _validate_candidate_sql(candidate: OptimizationRecommendation) -> None:
    if candidate.suggested_sql != _deterministic_candidate_sql(
        candidate.affected_table or "", candidate.affected_columns
    ):
        raise CandidateValidationError(
            "Candidate SQL does not exactly match the deterministic recommendation."
        )


def _validate_candidate_database(connection, candidate: OptimizationRecommendation) -> None:
    table = candidate.affected_table
    if table is None:
        raise CandidateValidationError("Candidate table is required.")
    _validate_identifier(table, "candidate table")
    if not candidate.affected_columns:
        raise CandidateValidationError("At least one candidate column is required.")
    for column in candidate.affected_columns:
        _validate_identifier(column, "candidate column")

    inspector = inspect(connection)
    if not inspector.has_table(table):
        raise CandidateValidationError(f"Candidate table does not exist: {table}")
    table_columns = {column["name"] for column in inspector.get_columns(table)}
    missing = [column for column in candidate.affected_columns if column not in table_columns]
    if missing:
        raise CandidateValidationError(
            f"Candidate columns do not exist on {table}: {', '.join(missing)}"
        )


def validate_candidate(
    connection,
    candidate: OptimizationRecommendation,
) -> tuple[str, str, list[str]]:
    """Validate a deterministic candidate and return its controlled index name."""

    if candidate.type != _SUPPORTED_CANDIDATE:
        raise CandidateValidationError(f"Unsupported candidate type: {candidate.type}")
    _validate_candidate_database(connection, candidate)
    _validate_candidate_sql(candidate)
    table = candidate.affected_table
    assert table is not None
    return table, _benchmark_index_name(table, candidate.affected_columns), candidate.affected_columns


def _index_state(connection, table: str, columns: list[str], index_name: str) -> tuple[bool, bool]:
    """Return whether an equivalent index and exact index name already exist."""

    rows = connection.execute(
        text(
            """
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE schemaname = current_schema() AND tablename = :table_name
            """
        ),
        {"table_name": table},
    ).mappings().all()
    expected_columns = ", ".join(columns)
    equivalent = any(
        re.search(rf"\({re.escape(expected_columns)}\)\s*$", row["indexdef"], re.IGNORECASE)
        for row in rows
    )
    exact_name = any(row["indexname"] == index_name for row in rows)
    return equivalent, exact_name


def _set_timeout(connection, timeout_ms: int) -> None:
    if timeout_ms <= 0:
        raise BenchmarkError("Benchmark timeout must be positive.")
    connection.execute(
        text(
            "SELECT set_config('statement_timeout', CAST(:timeout_ms AS text), false)"
        ),
        {"timeout_ms": str(timeout_ms)},
    )


class BenchmarkService:
    """Run a synchronous, temporary-index before/after benchmark."""

    def __init__(
        self,
        engine: Engine | None = None,
        explain_service: ExplainService | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._engine = engine or get_engine()
        self._explain_service = explain_service or ExplainService(self._engine)
        self._settings = settings or get_settings()

    def _measure(
        self,
        query: str,
        repetitions: int,
        warmup_runs: int,
        timeout_ms: int,
    ) -> BenchmarkMeasurement:
        if repetitions <= 0 or warmup_runs < 0:
            raise BenchmarkError("Repetitions must be positive and warmup runs cannot be negative.")
        for _ in range(warmup_runs):
            self._explain_service.explain(query, statement_timeout_ms=timeout_ms)
        results = [
            self._explain_service.explain(query, statement_timeout_ms=timeout_ms)
            for _ in range(repetitions)
        ]
        if not results:
            raise BenchmarkError("No benchmark measurements were collected.")
        nodes = [_measurement_node(result) for result in results]
        execution_times = [result.execution_time_ms for result in results]
        planning_times = [result.planning_time_ms for result in results]
        if any(value is None or value < 0 for value in execution_times + planning_times):
            raise BenchmarkError("PostgreSQL returned an invalid benchmark timing.")
        node = nodes[-1]
        buffers = node.buffers
        return BenchmarkMeasurement(
            execution_times_ms=[value for value in execution_times if value is not None],
            median_execution_time_ms=calculate_median([value for value in execution_times if value is not None]),
            mean_execution_time_ms=calculate_mean([value for value in execution_times if value is not None]),
            planning_times_ms=[value for value in planning_times if value is not None],
            median_planning_time_ms=calculate_median([value for value in planning_times if value is not None]),
            node_type=node.node_type,
            relation_name=node.relation,
            index_name=node.index_name,
            actual_rows=node.actual_rows,
            planned_rows=node.planned_rows,
            shared_hit_blocks=buffers.shared_hit_blocks if buffers else None,
            shared_read_blocks=buffers.shared_read_blocks if buffers else None,
        )

    def benchmark(
        self,
        query: str,
        candidate: OptimizationRecommendation,
        *,
        repetitions: int | None = None,
        warmup_runs: int | None = None,
    ) -> BenchmarkResult:
        """Measure a SELECT before and after one validated temporary index."""

        safe_query = validate_select_query(query)
        repetitions = self._settings.benchmark_repetitions if repetitions is None else repetitions
        warmup_runs = self._settings.benchmark_warmup_runs if warmup_runs is None else warmup_runs
        timeout_ms = self._settings.benchmark_timeout_ms
        created_index = False
        result: BenchmarkResult | None = None
        table = candidate.affected_table or ""
        columns = candidate.affected_columns
        index_name = _benchmark_index_name(table, columns)
        try:
            with self._engine.connect() as connection:
                _set_timeout(connection, timeout_ms)
                table, index_name, columns = validate_candidate(connection, candidate)
            baseline = self._measure(safe_query, repetitions, warmup_runs, timeout_ms)

            with self._engine.begin() as connection:
                _set_timeout(connection, timeout_ms)
                equivalent, exact_name = _index_state(connection, table, columns, index_name)
                if exact_name and not equivalent:
                    raise BenchmarkError(f"Controlled index name already exists: {index_name}")
                if not equivalent:
                    connection.execute(
                        text(
                            f"CREATE INDEX {index_name} ON {table} "
                            f"({', '.join(columns)})"
                        )
                    )
                    created_index = True

            with self._engine.begin() as connection:
                _set_timeout(connection, timeout_ms)
                connection.execute(text(f"ANALYZE {table}"))

            after = self._measure(safe_query, repetitions, warmup_runs, timeout_ms)
            improvement = calculate_improvement_percent(
                baseline.median_execution_time_ms,
                after.median_execution_time_ms,
            )
            comparison = BenchmarkComparison(
                baseline_median_execution_time_ms=baseline.median_execution_time_ms,
                after_median_execution_time_ms=after.median_execution_time_ms,
                execution_time_delta_ms=(
                    after.median_execution_time_ms - baseline.median_execution_time_ms
                    if baseline.median_execution_time_ms is not None
                    and after.median_execution_time_ms is not None
                    else None
                ),
                improvement_percent=improvement,
                classification=classify_improvement(
                    improvement, self._settings.benchmark_min_improvement_percent
                ),
                scan_type_changed=baseline.node_type != after.node_type,
            )
            result = BenchmarkResult(
                original_query=safe_query,
                candidate_type=candidate.type,
                candidate_table=table,
                candidate_columns=columns,
                candidate_index_name=index_name,
                repetitions=repetitions,
                warmup_runs=warmup_runs,
                baseline=baseline,
                after=after,
                comparison=comparison,
                cleanup_completed=False,
            )
        except SQLAlchemyError as exc:
            raise BenchmarkError("PostgreSQL benchmark operation failed.") from exc
        finally:
            try:
                if created_index:
                    with self._engine.begin() as connection:
                        _set_timeout(connection, timeout_ms)
                        connection.execute(text(f"DROP INDEX IF EXISTS {index_name}"))
            except SQLAlchemyError as exc:
                raise BenchmarkError("Benchmark cleanup failed; the controlled index may remain.") from exc
            if result is not None:
                result.cleanup_completed = True
        if result is None:
            raise BenchmarkError("Benchmark did not produce a result.")
        return result


__all__ = [
    "BenchmarkComparison",
    "BenchmarkError",
    "BenchmarkMeasurement",
    "BenchmarkResult",
    "BenchmarkService",
    "CandidateValidationError",
    "calculate_improvement_percent",
    "calculate_mean",
    "calculate_median",
    "classify_improvement",
    "validate_candidate",
]