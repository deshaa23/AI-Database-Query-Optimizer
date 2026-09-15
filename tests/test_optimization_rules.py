"""Unit tests for deterministic optimization recommendations."""

from app.optimizer.models import ExplainResult, PlanNode
from app.optimizer.rules import OptimizationRuleEngine


def _result(plan: PlanNode, execution_time_ms: float = 50.0) -> ExplainResult:
    return ExplainResult(query="SELECT 1", plan=plan, execution_time_ms=execution_time_ms)


def test_filtered_sequential_scan_produces_index_candidate() -> None:
    plan = PlanNode(
        node_type="Seq Scan",
        relation="orders",
        filter="(user_id = 4242)",
        actual_total_time=4.0,
        actual_rows=12,
        actual_loops=1,
    )

    recommendations = OptimizationRuleEngine().recommend(_result(plan))

    assert len(recommendations) == 1
    recommendation = recommendations[0]
    assert recommendation.type == "MISSING_INDEX_CANDIDATE"
    assert recommendation.affected_table == "orders"
    assert recommendation.affected_columns == ["user_id"]
    assert recommendation.suggested_sql == (
        "CREATE INDEX idx_orders_user_id ON orders(user_id);"
    )


def test_unfiltered_sequential_scan_is_not_automatically_an_index_candidate() -> None:
    plan = PlanNode(
        node_type="Seq Scan",
        relation="orders",
        actual_total_time=25.0,
        actual_rows=500000,
        actual_loops=1,
    )

    recommendations = OptimizationRuleEngine().recommend(_result(plan, 50.0))

    assert len(recommendations) == 1
    assert recommendations[0].type == "PERFORMANCE_BOTTLENECK"
    assert recommendations[0].suggested_sql is None


def test_expensive_sequential_scan_is_reported_with_evidence() -> None:
    plan = PlanNode(
        node_type="Seq Scan",
        relation="orders",
        actual_total_time=80.0,
        actual_rows=500000,
        actual_loops=1,
    )

    recommendation = OptimizationRuleEngine().recommend(_result(plan, 100.0))[0]

    assert recommendation.type == "PERFORMANCE_BOTTLENECK"
    assert recommendation.affected_table == "orders"
    assert "actual total time of 80.000 ms per loop across 1 loops" in recommendation.description
    assert "approximately 80.000 ms cumulative" in recommendation.description
    assert any("Actual rows" in evidence for evidence in recommendation.evidence)


def test_bottleneck_wording_distinguishes_per_loop_and_cumulative_time() -> None:
    plan = PlanNode(
        node_type="Seq Scan",
        relation="orders",
        actual_total_time=14.548,
        actual_rows=3,
        actual_loops=3,
    )

    recommendation = OptimizationRuleEngine().recommend(_result(plan, 100.0))[0]

    assert recommendation.type == "PERFORMANCE_BOTTLENECK"
    assert "actual total time of 14.548 ms per loop across 3 loops" in recommendation.description
    assert "approximately 43.644 ms cumulative" in recommendation.description


def test_sort_with_unambiguous_table_and_key_produces_candidate() -> None:
    plan = PlanNode(
        node_type="Sort",
        sort_keys=["created_at"],
        plans=[PlanNode(node_type="Seq Scan", relation="orders")],
    )

    recommendation = OptimizationRuleEngine().recommend(_result(plan))[0]

    assert recommendation.type == "MISSING_INDEX_CANDIDATE"
    assert recommendation.suggested_sql == (
        "CREATE INDEX idx_orders_created_at ON orders(created_at);"
    )


def test_sort_without_enough_evidence_has_no_speculative_sql() -> None:
    plan = PlanNode(
        node_type="Sort",
        sort_keys=["(created_at DESC)"],
        plans=[
            PlanNode(node_type="Seq Scan", relation="orders"),
            PlanNode(node_type="Seq Scan", relation="users"),
        ],
    )

    recommendation = OptimizationRuleEngine().recommend(_result(plan))[0]

    assert recommendation.type == "PERFORMANCE_BOTTLENECK"
    assert recommendation.suggested_sql is None


def test_duplicate_plan_nodes_produce_deduplicated_recommendations() -> None:
    plan = PlanNode(
        node_type="Append",
        plans=[
            PlanNode(node_type="Seq Scan", relation="orders", filter="user_id = 4242"),
            PlanNode(node_type="Seq Scan", relation="orders", filter="user_id = 4242"),
        ],
    )

    recommendations = OptimizationRuleEngine().recommend(_result(plan))

    assert len(recommendations) == 1
    assert recommendations[0].affected_columns == ["user_id"]


def test_confidence_is_bounded_and_rule_engine_does_not_execute_sql() -> None:
    plan = PlanNode(node_type="Seq Scan", relation="orders", filter="user_id = 4242")

    recommendations = OptimizationRuleEngine().recommend(_result(plan))

    assert all(0.0 <= recommendation.confidence <= 1.0 for recommendation in recommendations)
    assert all(recommendation.suggested_sql is not None for recommendation in recommendations)


def test_complex_filter_does_not_produce_unsafe_index_sql() -> None:
    plan = PlanNode(
        node_type="Seq Scan",
        relation="orders",
        filter="(user_id = 4242 AND status = 'paid')",
    )

    recommendations = OptimizationRuleEngine().recommend(_result(plan))

    assert recommendations == []