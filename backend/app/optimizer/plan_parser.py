"""Parse and inspect PostgreSQL EXPLAIN JSON plans."""

from collections.abc import Mapping
from typing import Any

from app.optimizer.models import BufferInfo, ExplainResult, PlanNode, PlanObservation


def _parse_buffers(raw_buffers: Mapping[str, Any] | None) -> BufferInfo | None:
    if not raw_buffers:
        return None

    key_map = {
        "Shared Hit Blocks": "shared_hit_blocks",
        "Shared Read Blocks": "shared_read_blocks",
        "Shared Dirtied Blocks": "shared_dirtied_blocks",
        "Shared Written Blocks": "shared_written_blocks",
        "Local Hit Blocks": "local_hit_blocks",
        "Local Read Blocks": "local_read_blocks",
        "Local Dirtied Blocks": "local_dirtied_blocks",
        "Local Written Blocks": "local_written_blocks",
        "Temp Read Blocks": "temp_read_blocks",
        "Temp Written Blocks": "temp_written_blocks",
    }
    return BufferInfo.model_validate(
        {key_map[key]: value for key, value in raw_buffers.items() if key in key_map}
    )


def parse_plan(raw_node: Mapping[str, Any]) -> PlanNode:
    """Recursively convert one PostgreSQL plan node into a Pydantic model."""

    return PlanNode(
        node_type=raw_node["Node Type"],
        relation=raw_node.get("Relation Name"),
        startup_cost=raw_node.get("Startup Cost"),
        total_cost=raw_node.get("Total Cost"),
        actual_startup_time=raw_node.get("Actual Startup Time"),
        actual_total_time=raw_node.get("Actual Total Time"),
        planned_rows=raw_node.get("Plan Rows"),
        actual_rows=raw_node.get("Actual Rows"),
        actual_loops=raw_node.get("Actual Loops"),
        index_name=raw_node.get("Index Name"),
        filter=raw_node.get("Filter"),
        buffers=_parse_buffers(raw_node.get("Buffers")),
        plans=[parse_plan(child) for child in raw_node.get("Plans", [])],
    )


def parse_explain_json(raw_explain: list[Mapping[str, Any]] | Mapping[str, Any]) -> ExplainResult:
    """Parse the JSON document returned by PostgreSQL FORMAT JSON."""

    document = raw_explain[0] if isinstance(raw_explain, list) else raw_explain
    return ExplainResult(
        query="",
        plan=parse_plan(document["Plan"]),
        planning_time_ms=document.get("Planning Time"),
        execution_time_ms=document.get("Execution Time"),
    )


def analyze_plan(
    plan: PlanNode,
    *,
    expensive_threshold_ms: float = 100.0,
    row_discrepancy_ratio: float = 10.0,
) -> list[PlanObservation]:
    """Detect basic plan characteristics without making tuning recommendations."""

    observations: list[PlanObservation] = []

    def visit(node: PlanNode) -> None:
        if node.node_type == "Seq Scan":
            observations.append(
                PlanObservation(
                    type="sequential_scan",
                    severity="medium",
                    message="Sequential scan detected.",
                    node_type=node.node_type,
                    relation=node.relation,
                )
            )
        elif node.node_type == "Index Scan":
            observations.append(
                PlanObservation(
                    type="index_scan",
                    severity="low",
                    message="Index scan detected.",
                    node_type=node.node_type,
                    relation=node.relation,
                )
            )
        elif node.node_type == "Index Only Scan":
            observations.append(
                PlanObservation(
                    type="index_only_scan",
                    severity="low",
                    message="Index-only scan detected.",
                    node_type=node.node_type,
                    relation=node.relation,
                )
            )
        elif node.node_type == "Sort":
            observations.append(
                PlanObservation(
                    type="sort",
                    severity="low",
                    message="Explicit sort operation detected.",
                    node_type=node.node_type,
                    relation=node.relation,
                )
            )

        if (
            node.planned_rows
            and node.planned_rows > 0
            and node.actual_rows is not None
            and (
                node.actual_rows / node.planned_rows >= row_discrepancy_ratio
                or node.planned_rows / max(node.actual_rows, 1) >= row_discrepancy_ratio
            )
        ):
            observations.append(
                PlanObservation(
                    type="row_estimate_discrepancy",
                    severity="medium",
                    message=(
                        f"Estimated {node.planned_rows:g} rows but observed "
                        f"{node.actual_rows:g} rows."
                    ),
                    node_type=node.node_type,
                    relation=node.relation,
                )
            )

        if node.actual_total_time is not None and node.actual_total_time >= expensive_threshold_ms:
            observations.append(
                PlanObservation(
                    type="expensive_node",
                    severity="high",
                    message=(
                        f"Node took {node.actual_total_time:.2f} ms per loop, exceeding "
                        f"the {expensive_threshold_ms:.2f} ms threshold."
                    ),
                    node_type=node.node_type,
                    relation=node.relation,
                )
            )

        for child in node.plans:
            visit(child)

    visit(plan)
    return observations