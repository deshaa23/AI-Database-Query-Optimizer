# AI Database Query Optimizer

AI Database Query Optimizer is a portfolio project for analyzing SQL queries and PostgreSQL execution plans, recommending performance improvements, and validating recommendations through measured benchmarks.

## Current functionality

Milestone 2 provides a small FastAPI backend foundation with:

- Environment-based application settings using `pydantic-settings`
- SQLAlchemy 2.x connectivity to PostgreSQL using the `psycopg` driver
- `GET /api/v1/health`, which reports application and database status
- Unit tests for healthy and degraded database status
- An opt-in PostgreSQL integration test

SQL parsing, optimization recommendations, benchmarking, AI components, and the frontend will be added in later milestones.

## Execution-plan analysis

Milestone 4 provides a SELECT-only execution-plan analyzer through `ExplainService.explain(query)`. It runs PostgreSQL `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)`, so PostgreSQL executes the query and reports actual timing and buffer activity without changing data. JSON output gives QueryForge a stable, recursive representation of plan nodes that can later feed the optimization engine for observations and recommendations.

For example, after initializing the benchmark database:

```python
from app.optimizer.explain import ExplainService

result = ExplainService().explain(
	"SELECT id, created_at FROM orders WHERE user_id = 4242"
)
print(result.plan.node_type, result.execution_time_ms)
```

The analyzer currently reports basic scans, sorts, row-estimate discrepancies, and expensive nodes. It does not create indexes, rewrite SQL, or use AI.

## Deterministic optimization recommendations

Milestone 5 applies deterministic rules to the `ExplainResult` and its recursive `PlanNode` tree. Recommendations are based on measured execution-plan evidence, such as a filtered sequential scan, a costly scan, or an explicit sort. An observation describes what PostgreSQL did; a recommendation identifies a possible action only when the plan provides enough evidence.

Suggested index statements are output for review only. QueryForge never executes `CREATE INDEX` or any other optimization SQL automatically, preserving a clean before-optimization baseline for later validation.

## Requirements

- Python 3.11 or newer
- Docker Desktop with Docker Compose
- PostgreSQL is provided by Docker Compose; a local PostgreSQL installation is not required

## Setup

Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install the project and test dependencies:

```powershell
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
```

Copy the safe environment template and set a local PostgreSQL password:

```powershell
Copy-Item .env.example .env
```

Edit `.env` as needed. `.env` is ignored by Git and must not contain committed secrets.

Start PostgreSQL with Docker Compose:

```powershell
docker compose up -d postgres
docker compose ps
```

Stop PostgreSQL without removing its persisted data:

```powershell
docker compose stop postgres
```

To stop and remove the container while retaining the named volume:

```powershell
docker compose down
```

## Run the application

```powershell
uvicorn app.main:app --app-dir backend --reload
```

The health endpoint is available at <http://127.0.0.1:8000/api/v1/health>.

## Run tests

```powershell
python -m pytest
```

The default test command does not require PostgreSQL to be running. Run the PostgreSQL integration test explicitly after starting Docker Compose:

```powershell
$env:RUN_INTEGRATION_TESTS = "1"
python -m pytest -m integration
```

The backend connects using the PostgreSQL values in `.env` and can be started with:

```powershell
uvicorn app.main:app --app-dir backend --reload
```
