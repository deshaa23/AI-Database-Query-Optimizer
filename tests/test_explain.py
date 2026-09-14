"""Unit tests for SELECT-only execution-plan validation."""

import pytest

from app.optimizer.explain import InvalidQueryError, validate_select_query


def test_accepts_one_select_statement_with_optional_trailing_semicolon() -> None:
    assert validate_select_query(" SELECT id FROM users; ") == "SELECT id FROM users"


@pytest.mark.parametrize(
    "query",
    [
        "INSERT INTO users (name) VALUES ('blocked')",
        "UPDATE users SET name = 'blocked'",
        "DELETE FROM users",
        "DROP TABLE users",
        "SELECT 1; SELECT 2",
    ],
)
def test_rejects_non_select_and_multiple_statements(query: str) -> None:
    with pytest.raises(InvalidQueryError):
        validate_select_query(query)