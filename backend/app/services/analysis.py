"""Orchestration for the QueryForge analysis workflow."""

from sqlalchemy.exc import SQLAlchemyError

from app.ai.optimizer import AIOptimizer
from app.ai.provider import OpenAIProvider
from app.ai.schemas import OptimizationAnalysis
from app.core.config import Settings, get_settings
from app.optimizer.benchmark import BenchmarkError, BenchmarkResult, BenchmarkService
from app.optimizer.explain import ExplainService
from app.optimizer.models import ExplainResult, OptimizationRecommendation
from app.optimizer.rules import OptimizationRuleEngine


class AnalysisError(RuntimeError):
    """Base error for controlled analysis failures."""


class AIAnalysisError(AnalysisError):
    """Raised when optional AI analysis cannot be completed."""


class BenchmarkAnalysisError(AnalysisError):
    """Raised when an explicitly requested benchmark cannot be completed."""


class AnalysisService:
    """Compose existing optimizer services without owning database or AI logic."""

    def __init__(
        self,
        explain_service: ExplainService | None = None,
        rule_engine: OptimizationRuleEngine | None = None,
        ai_optimizer: AIOptimizer | None = None,
        benchmark_service: BenchmarkService | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._explain_service = explain_service or ExplainService()
        self._rule_engine = rule_engine or OptimizationRuleEngine()
        self._ai_optimizer = ai_optimizer
        self._benchmark_service = benchmark_service or BenchmarkService()
        self._settings = settings or get_settings()

    def analyze(
        self,
        *,
        query: str,
        include_ai: bool,
        include_benchmark: bool,
    ) -> tuple[ExplainResult, list[OptimizationRecommendation], OptimizationAnalysis | None, BenchmarkResult | None]:
        """Run the requested analysis stages in order."""

        try:
            explain_result = self._explain_service.explain(query)
            recommendations = self._rule_engine.recommend(explain_result)
        except SQLAlchemyError as exc:
            raise AnalysisError("Database analysis failed.") from exc

        ai_analysis = None
        if include_ai:
            try:
                ai_optimizer = self._ai_optimizer or AIOptimizer(
                    OpenAIProvider(settings=self._settings)
                )
                ai_analysis = ai_optimizer.analyze(
                    query=query,
                    explain_result=explain_result,
                    recommendations=recommendations,
                )
            except Exception as exc:
                if isinstance(exc, AnalysisError):
                    raise
                raise AIAnalysisError("AI analysis is currently unavailable.") from exc

        benchmark = None
        if include_benchmark:
            candidate = next(
                (
                    recommendation
                    for recommendation in recommendations
                    if recommendation.type == "MISSING_INDEX_CANDIDATE"
                    and recommendation.suggested_sql
                ),
                None,
            )
            if candidate is not None:
                try:
                    benchmark = self._benchmark_service.benchmark(query, candidate)
                except BenchmarkError as exc:
                    raise BenchmarkAnalysisError("Benchmark execution failed.") from exc

        return explain_result, recommendations, ai_analysis, benchmark