"""Deterministic optimization recommendations from parsed execution plans."""

import re
from collections.abc import Iterator

from app.optimizer.models import ExplainResult, OptimizationRecommendation, PlanNode


_EQUALITY_PREDICATE = re.compile(
    r"^\(?\s*(?:[\w]+\.)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*"
    r"(?:\$[0-9]+|'(?:''|[^'])*'|[-+]?[0-9]+(?:\.[0-9]+)?)\s*\)?$"
)
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _walk(node: PlanNode) -> Iterator[PlanNode]:
    yield node
    for child in node.plans:
        yield from _walk(child)


def _simple_equality_column(filter_text: str | None) -> str | None:
    """Return a column only for a simple, safe equality predicate."""

    if not filter_text:
        return None
    match = _EQUALITY_PREDICATE.fullmatch(filter_text.strip())
    return match.group(1) if match else None


def _descendant_tables(node: PlanNode) -> set[str]:
    return {child.relation for child in _walk(node) if child.relation is not None}


def _index_name(table: str, columns: list[str]) -> str:
    return "idx_" + "_".join([table, *columns])


class OptimizationRuleEngine:
    """Turn plan evidence into explainable recommendations without DB access."""

    def __init__(self, *, expensive_share: float = 0.25, expensive_floor_ms: float = 10.0):
        self._expensive_share = expensive_share
        self._expensive_floor_ms = expensive_floor_ms

    def recommend(self, explain_result: ExplainResult) -> list[OptimizationRecommendation]:
        """Apply all rules and return deduplicated recommendations."""

        recommendations: list[OptimizationRecommendation] = []
        seen: set[tuple[str, str | None, tuple[str, ...]]] = set()
        total_time = explain_result.execution_time_ms

        def add(recommendation: OptimizationRecommendation) -> None:
            key = (
                recommendation.type,
                recommendation.affected_table,
                tuple(recommendation.affected_columns),
            )
            if key not in seen:
                seen.add(key)
                recommendations.append(recommendation)

        for node in _walk(explain_result.plan):
            if node.node_type == "Seq Scan":
                column = _simple_equality_column(node.filter)
                if node.relation and column:
                    add(
                        OptimizationRecommendation(
                            type="MISSING_INDEX_CANDIDATE",
                            severity="medium",
                            title="Consider an index for the filtered sequential scan",
                            description=(
                                f"The plan scans {node.relation} sequentially while filtering "
                                f"on {column}. An index may reduce rows that must be scanned."
                            ),
                            rationale="A simple equality filter identifies a concrete index candidate.",
                            evidence=[
                                f"Node Type: {node.node_type}",
                                f"Relation: {node.relation}",
                                f"Filter: {node.filter}",
                            ],
                            affected_table=node.relation,
                            affected_columns=[column],
                            suggested_sql=(
                                f"CREATE INDEX {_index_name(node.relation, [column])} "
                                f"ON {node.relation}({column});"
                            ),
                            confidence=0.8,
                        )
                    )

                node_time = (node.actual_total_time or 0.0) * (node.actual_loops or 1.0)
                significant = node_time >= self._expensive_floor_ms and (
                    total_time is None or node_time >= total_time * self._expensive_share
                )
                if significant:
                    add(
                        OptimizationRecommendation(
                            type="PERFORMANCE_BOTTLENECK",
                            severity="high" if total_time and node_time >= total_time * 0.5 else "medium",
                            title="Expensive sequential scan",
                            description=(
                                f"The sequential scan on {node.relation or 'an unknown table'} "
                                f"consumed {node_time:.2f} ms."
                            ),
                            rationale="The scan accounts for a significant measured portion of execution time.",
                            evidence=[
                                f"Actual total time: {node.actual_total_time} ms",
                                f"Actual rows per loop: {node.actual_rows}",
                                f"Actual loops: {node.actual_loops}",
                            ],
                            affected_table=node.relation,
                            confidence=0.9,
                        )
                    )

            elif node.node_type == "Sort":
                tables = _descendant_tables(node)
                sort_columns = [key for key in node.sort_keys if _IDENTIFIER.fullmatch(key)]
                table = next(iter(tables)) if len(tables) == 1 else None
                suggested_sql = None
                confidence = 0.6
                if table and sort_columns and len(sort_columns) == len(node.sort_keys):
                    suggested_sql = (
                        f"CREATE INDEX {_index_name(table, sort_columns)} "
                        f"ON {table}({', '.join(sort_columns)});"
                    )
                    confidence = 0.55
                add(
                    OptimizationRecommendation(
                        type="MISSING_INDEX_CANDIDATE" if suggested_sql else "PERFORMANCE_BOTTLENECK",
                        severity="low" if suggested_sql else "medium",
                        title="Sort operation may be avoidable" if suggested_sql else "Explicit sort operation",
                        description=(
                            "The plan contains an explicit sort operation."
                            + (" An index matching the sort key may help." if suggested_sql else "")
                        ),
                        rationale=(
                            "The sort key and a single underlying table provide enough evidence for a candidate."
                            if suggested_sql
                            else "The plan does not identify a safe table and simple sort-key combination."
                        ),
                        evidence=[
                            "Node Type: Sort",
                            f"Sort keys: {', '.join(node.sort_keys) or 'not reported'}",
                        ],
                        affected_table=table,
                        affected_columns=sort_columns,
                        suggested_sql=suggested_sql,
                        confidence=confidence,
                    )
                )

        return recommendations