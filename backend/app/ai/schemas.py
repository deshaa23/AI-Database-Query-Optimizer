"""Pydantic models for grounded AI optimization input and output."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.optimizer.models import OptimizationRecommendation, PlanObservation


class PlanSummaryNode(BaseModel):
    """Bounded plan evidence supplied to the model."""

    model_config = ConfigDict(extra="forbid")

    node_type: str
    relation: str | None = None
    filter: str | None = None
    sort_keys: list[str] = Field(default_factory=list)
    actual_total_time_ms: float | None = None
    actual_rows: float | None = None
    actual_loops: float | None = None
    children: list["PlanSummaryNode"] = Field(default_factory=list)


class AIInput(BaseModel):
    """Facts and deterministic candidates provided to an AI provider."""

    model_config = ConfigDict(extra="forbid")

    original_query: str
    execution_time_ms: float | None = None
    planning_time_ms: float | None = None
    execution_plan_summary: PlanSummaryNode
    observations: list[PlanObservation]
    deterministic_recommendations: list[OptimizationRecommendation]


class AIRecommendation(BaseModel):
    """An AI explanation of one deterministic recommendation."""

    model_config = ConfigDict(extra="forbid")

    recommendation_type: Literal["MISSING_INDEX_CANDIDATE", "PERFORMANCE_BOTTLENECK"]
    title: str
    explanation: str
    rationale: str
    affected_table: str | None = None
    affected_columns: list[str] = Field(default_factory=list)
    suggested_sql: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)


class OptimizationAnalysis(BaseModel):
    """Validated AI ranking and explanation of deterministic candidates."""

    model_config = ConfigDict(extra="forbid")

    summary: str
    primary_recommendation: str | None = None
    ranked_recommendations: list[AIRecommendation]
    tradeoffs: list[str]
    confidence: float = Field(ge=0.0, le=1.0)
    validation_steps: list[str]