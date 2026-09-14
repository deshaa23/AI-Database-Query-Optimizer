"""Service for safely collecting PostgreSQL execution plans."""

from typing import Any

from sqlalchemy import Engine, text

from app.db.connection import get_engine
from app.optimizer.models import ExplainResult
from app.optimizer.plan_parser import analyze_plan, parse_explain_json


class InvalidQueryError(ValueError):
    """Raised when a query is not one safe, top-level SELECT statement."""


def validate_select_query(query: str) -> str:
    """Validate and normalize a single SELECT statement."""

    normalized = query.strip()
    if normalized.endswith(";"):
        normalized = normalized[:-1].rstrip()
    if not normalized or ";" in normalized:
        raise InvalidQueryError("Only one SELECT statement is allowed.")
    if not normalized.upper().startswith("SELECT"):
        raise InvalidQueryError("Only SELECT statements are allowed.")
    if len(normalized) > 6 and not normalized[6].isspace() and normalized[6] != "(":
        raise InvalidQueryError("Only SELECT statements are allowed.")
    return normalized


class ExplainService:
    """Execute and analyze PostgreSQL EXPLAIN JSON for SELECT statements."""

    def __init__(self, engine: Engine | None = None) -> None:
        self._engine = engine or get_engine()

    def explain(self, query: str) -> ExplainResult:
        """Return a parsed, analyzed execution plan without modifying data."""

        safe_query = validate_select_query(query)
        explain_query = text(
            f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {safe_query}"
        )
        with self._engine.connect() as connection:
            raw_plan: Any = connection.execute(explain_query).scalar_one()

        result = parse_explain_json(raw_plan)
        result.query = safe_query
        result.observations = analyze_plan(result.plan)
        return result