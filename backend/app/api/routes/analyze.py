"""REST endpoint for QueryForge SQL analysis."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.ai.provider import AIProviderError
from app.api.schemas import AnalyzeRequest, AnalyzeResponse
from app.services.analysis import (
    AIAnalysisError,
    AnalysisError,
    AnalysisService,
    BenchmarkAnalysisError,
)
from app.optimizer.explain import InvalidQueryError


router = APIRouter()


def get_analysis_service() -> AnalysisService:
    """Provide the default analysis orchestration service."""

    return AnalysisService()


@router.post(
    "/analyze",
    response_model=AnalyzeResponse,
    status_code=status.HTTP_200_OK,
    summary="Analyze a PostgreSQL SELECT query",
    description=(
        "Run EXPLAIN ANALYZE, deterministic optimization rules, and optional grounded AI "
        "reasoning or benchmarking for one SELECT statement."
    ),
    responses={
        400: {"description": "Invalid or unsupported SQL query."},
        422: {"description": "Malformed request body."},
        500: {"description": "Database, benchmark, or unexpected analysis failure."},
        503: {"description": "AI provider is unavailable or misconfigured."},
    },
)
def analyze_query(
    request: AnalyzeRequest,
    service: AnalysisService = Depends(get_analysis_service),
) -> AnalyzeResponse:
    """Analyze one safe SELECT query through the existing optimizer services."""

    try:
        explain_result, recommendations, ai_analysis, benchmark = service.analyze(
            query=request.query,
            include_ai=request.include_ai,
            include_benchmark=request.include_benchmark,
        )
    except InvalidQueryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (AIAnalysisError, AIProviderError) as exc:
        raise HTTPException(status_code=503, detail="AI analysis is unavailable.") from exc
    except BenchmarkAnalysisError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except (AnalysisError, SQLAlchemyError) as exc:
        raise HTTPException(status_code=500, detail="Analysis could not be completed.") from exc
    except ValidationError as exc:
        raise HTTPException(status_code=500, detail="Analysis returned invalid structured data.") from exc

    return AnalyzeResponse(
        query=explain_result.query,
        execution_plan=explain_result,
        observations=explain_result.observations,
        deterministic_recommendations=recommendations,
        ai_analysis=ai_analysis,
        benchmark=benchmark,
        benchmark_note=(
            "No supported deterministic benchmark candidate was available."
            if request.include_benchmark and benchmark is None
            else None
        ),
    )