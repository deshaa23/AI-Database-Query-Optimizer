"""Pydantic schemas for the public API."""

from pydantic import BaseModel, ConfigDict, Field

from app.ai.schemas import OptimizationAnalysis
from app.optimizer.benchmark import BenchmarkResult
from app.optimizer.models import ExplainResult, OptimizationRecommendation, PlanObservation


class AnalyzeRequest(BaseModel):
    """Options accepted by the SQL analysis endpoint."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=10000)
    include_ai: bool = True
    include_benchmark: bool = False


class AnalyzeResponse(BaseModel):
    """Structured result of SQL plan and optimization analysis."""

    query: str
    execution_plan: ExplainResult
    observations: list[PlanObservation]
    deterministic_recommendations: list[OptimizationRecommendation]
    ai_analysis: OptimizationAnalysis | None = None
    ai_note: str | None = None
    benchmark: BenchmarkResult | None = None
    benchmark_note: str | None = None