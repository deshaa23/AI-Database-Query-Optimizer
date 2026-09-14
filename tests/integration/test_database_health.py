"""Integration tests for PostgreSQL connectivity."""

import os

import pytest

from app.db.health import check_database_health


@pytest.mark.integration
def test_database_health() -> None:
    """PostgreSQL responds to the database health query."""

    if os.getenv("RUN_INTEGRATION_TESTS") != "1":
        pytest.skip("Set RUN_INTEGRATION_TESTS=1 to run PostgreSQL integration tests")

    assert check_database_health() is True
