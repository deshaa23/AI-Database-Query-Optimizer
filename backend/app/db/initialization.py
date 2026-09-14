"""Initialize and seed the PostgreSQL benchmark database."""

from argparse import ArgumentParser
from pathlib import Path

from sqlalchemy import text

from app.db.connection import get_engine


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATABASE_INIT_DIR = PROJECT_ROOT / "database" / "init"


def _run_sql_file(connection, path: Path) -> None:
    """Execute the semicolon-delimited statements in a checked-in SQL file."""

    for statement in path.read_text(encoding="utf-8").split(";"):
        statement = statement.strip()
        if statement:
            connection.execute(text(statement))


def initialize_database(*, reset: bool = False) -> None:
    """Create the benchmark schema and seed it when it is empty.

    Pass ``reset=True`` to replace existing benchmark data before seeding.
    """

    with get_engine().begin() as connection:
        _run_sql_file(connection, DATABASE_INIT_DIR / "001_schema.sql")
        if reset:
            connection.execute(
                text("TRUNCATE TABLE orders, products, users RESTART IDENTITY CASCADE")
            )
        _run_sql_file(connection, DATABASE_INIT_DIR / "002_seed.sql")


def main() -> None:
    """Run database initialization from the command line."""

    parser = ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Remove existing benchmark rows before recreating and seeding them",
    )
    args = parser.parse_args()
    initialize_database(reset=args.reset)
    print("Benchmark database initialized.")


if __name__ == "__main__":
    main()