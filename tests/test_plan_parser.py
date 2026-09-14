"""Unit tests for PostgreSQL execution-plan parsing and observations."""

from app.optimizer.plan_parser import analyze_plan, parse_explain_json, parse_plan


def _scan_fixture(node_type: str, **values):
    return {
        "Plan": {
            "Node Type": node_type,
            "Relation Name": "orders",
            "Startup Cost": 0.0,
            "Total Cost": 100.0,
            "Actual Startup Time": 0.1,
            "Actual Total Time": values.pop("actual_time", 1.0),
            "Plan Rows": values.pop("planned_rows", 10),
            "Actual Rows": values.pop("actual_rows", 10),
            "Actual Loops": 1,
            **values,
        },
        "Planning Time": 0.2,
        "Execution Time": 1.1,
    }


def test_parses_sequential_scan_and_buffers() -> None:
    result = parse_explain_json(
        {
            **_scan_fixture("Seq Scan", Buffers={"Shared Hit Blocks": 12}),
        }
    )

    assert result.plan.node_type == "Seq Scan"
    assert result.plan.relation == "orders"
    assert result.plan.buffers is not None
    assert result.plan.buffers.shared_hit_blocks == 12


def test_parses_index_scan_details() -> None:
    result = parse_explain_json(
        _scan_fixture("Index Scan", **{"Index Name": "orders_user_id_idx"})
    )

    assert result.plan.index_name == "orders_user_id_idx"
    assert result.plan.actual_total_time == 1.0


def test_parses_nested_plan_nodes() -> None:
    raw_plan = _scan_fixture("Sort")
    raw_plan["Plan"]["Plans"] = [
        {
            "Node Type": "Index Only Scan",
            "Relation Name": "orders",
            "Index Name": "orders_pkey",
            "Plans": [],
        }
    ]

    result = parse_explain_json(raw_plan)

    assert result.plan.plans[0].node_type == "Index Only Scan"
    assert result.plan.plans[0].index_name == "orders_pkey"


def test_detects_sequential_scan_and_expensive_node() -> None:
    plan = parse_plan(_scan_fixture("Seq Scan", actual_time=125.0)["Plan"])

    observations = analyze_plan(plan)

    assert {observation.type for observation in observations} == {
        "sequential_scan",
        "expensive_node",
    }


def test_detects_estimated_vs_actual_row_discrepancy() -> None:
    plan = parse_plan(
        _scan_fixture("Seq Scan", planned_rows=100, actual_rows=2000)["Plan"]
    )

    observations = analyze_plan(plan)

    assert any(observation.type == "row_estimate_discrepancy" for observation in observations)