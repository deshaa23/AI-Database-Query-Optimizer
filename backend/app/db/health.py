"""Database connectivity checks."""

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.db.connection import get_engine


def check_database_health() -> bool:
    """Return whether PostgreSQL responds to a lightweight query."""

    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return False
    return True
