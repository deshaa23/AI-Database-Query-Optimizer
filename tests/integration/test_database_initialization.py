"""Integration tests for the benchmark database schema and seed data."""

import os

import pytest
from sqlalchemy import text

from app.db.connection import get_engine
from app.db.initialization import initialize_database


pytestmark = pytest.mark.integration


def _require_postgres() -> None:
    if os.getenv("RUN_INTEGRATION_TESTS") != "1":
        pytest.skip("Set RUN_INTEGRATION_TESTS=1 to run PostgreSQL integration tests")


def test_benchmark_database_initializes_from_an_empty_database() -> None:
    """Reset initialization creates the schema and expected dataset when empty."""

    _require_postgres()
    initialize_database(reset=True)

    with get_engine().connect() as connection:
        tables = connection.execute(
            text(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name IN ('users', 'products', 'orders')
                ORDER BY table_name
                """
            )
        ).scalars().all()
        counts = connection.execute(
            text(
                """
                SELECT
                    (SELECT COUNT(*) FROM users),
                    (SELECT COUNT(*) FROM products),
                    (SELECT COUNT(*) FROM orders)
                """
            )
        ).one()

    assert tables == ["orders", "products", "users"]
    assert counts == (50000, 10000, 500000)


def test_benchmark_initialization_is_repeatable_and_foreign_keys_are_valid() -> None:
    """A second initialization adds no rows and leaves relationships valid."""

    _require_postgres()
    initialize_database()

    with get_engine().connect() as connection:
        invalid_references = connection.execute(
            text(
                """
                SELECT
                    (SELECT COUNT(*) FROM orders o LEFT JOIN users u ON u.id = o.user_id
                     WHERE u.id IS NULL),
                    (SELECT COUNT(*) FROM orders o LEFT JOIN products p ON p.id = o.product_id
                     WHERE p.id IS NULL)
                """
            )
        ).one()
        counts = connection.execute(
            text(
                """
                SELECT
                    (SELECT COUNT(*) FROM users),
                    (SELECT COUNT(*) FROM products),
                    (SELECT COUNT(*) FROM orders)
                """
            )
        ).one()

    initialize_database()

    with get_engine().connect() as connection:
        repeated_counts = connection.execute(
            text(
                """
                SELECT
                    (SELECT COUNT(*) FROM users),
                    (SELECT COUNT(*) FROM products),
                    (SELECT COUNT(*) FROM orders)
                """
            )
        ).one()

    assert invalid_references == (0, 0)
    assert counts == (50000, 10000, 500000)
    assert repeated_counts == counts