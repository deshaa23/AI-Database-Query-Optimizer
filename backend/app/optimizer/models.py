"""Structured models for PostgreSQL EXPLAIN JSON output."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class BufferInfo(BaseModel):
    """Buffer activity reported for a plan node."""

    shared_hit_blocks: int | None = None
    shared_read_blocks: int | None = None
    shared_dirtied_blocks: int | None = None
    shared_written_blocks: int | None = None
    local_hit_blocks: int | None = None
    local_read_blocks: int | None = None
    local_dirtied_blocks: int | None = None
    local_written_blocks: int | None = None
    temp_read_blocks: int | None = None
    temp_written_blocks: int | None = None


class PlanNode(BaseModel):
    """A PostgreSQL plan node and its nested child nodes."""

    model_config = ConfigDict(extra="ignore")

    node_type: str
    relation: str | None = None
    startup_cost: float | None = None
    total_cost: float | None = None
    actual_startup_time: float | None = None
    actual_total_time: float | None = None
    planned_rows: float | None = None
    actual_rows: float | None = None
    actual_loops: float | None = None
    index_name: str | None = None
    filter: str | None = None
    buffers: BufferInfo | None = None
    plans: list["PlanNode"] = Field(default_factory=list)


class PlanObservation(BaseModel):
    """A basic fact detected from an execution plan."""

    type: Literal[
        "sequential_scan",
        "index_scan",
        "index_only_scan",
        "sort",
        "row_estimate_discrepancy",
        "expensive_node",
    ]
    severity: Literal["low", "medium", "high"]
    message: str
    node_type: str | None = None
    relation: str | None = None


class ExplainResult(BaseModel):
    """Parsed result returned by PostgreSQL EXPLAIN."""

    query: str
    plan: PlanNode
    planning_time_ms: float | None = None
    execution_time_ms: float | None = None
    observations: list[PlanObservation] = Field(default_factory=list)