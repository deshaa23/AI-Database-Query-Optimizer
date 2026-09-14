# AI Database Query Optimizer

[![CI](https://github.com/deshaa23/AI-Database-Query-Optimizer/actions/workflows/ci.yml/badge.svg)](https://github.com/deshaa23/AI-Database-Query-Optimizer/actions/workflows/ci.yml)

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

## AI-assisted optimization reasoning

Milestone 6 places AI after deterministic database analysis:

```text
Execution-plan evidence
	↓
Deterministic recommendation
	↓
AI explanation/ranking
	↓
Human validation
```

The AI receives the original query, measured planning and execution times, a bounded plan summary, deterministic observations, and deterministic recommendations. It may explain candidates, rank them, discuss tradeoffs, and suggest validation steps, but it cannot invent tables, columns, indexes, timings, or executable SQL. Any suggested SQL must exactly match SQL already produced by the deterministic rule engine. This grounding reduces hallucinations, while human review and before/after `EXPLAIN ANALYZE` remain required. QueryForge never automatically executes AI-generated SQL.

Configure the optional OpenAI provider without committing secrets:

```text
AI_PROVIDER=openai
AI_MODEL=<your-configured-model>
OPENAI_API_KEY=<your-local-key>
```

Unit tests use `MockLLMProvider`, so they do not require an API key or make network calls. The live provider is available through `OpenAIProvider` when the configuration is present.

## Performance Benchmarking

Milestone 7 measures a deterministic candidate with the same SELECT query before and after a controlled temporary index:

```text
SQL query
	-> baseline EXPLAIN ANALYZE
	-> deterministic optimization candidate
	-> controlled candidate index
	-> ANALYZE
	-> after EXPLAIN ANALYZE
	-> median comparison
	-> cleanup
```

Performance numbers come from PostgreSQL using `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)`. Each phase records individual timings plus mean and median values; median execution time is the primary comparison metric. The improvement percentage is calculated only from valid measured medians, and classifications use the configurable minimum threshold. Candidate indexes are derived only from validated deterministic recommendations, are temporary to the benchmark, and pre-existing indexes are preserved. Cleanup is attempted even when the after phase fails. LLM-generated SQL is never passed directly to this service, and a recommendation is not a guarantee that performance will improve.

Benchmark settings are configured through `BENCHMARK_TIMEOUT_MS`, `BENCHMARK_REPETITIONS`, `BENCHMARK_WARMUP_RUNS`, and `BENCHMARK_MIN_IMPROVEMENT_PERCENT` in the environment template. Example output should be interpreted as measured placeholders:

```text
Baseline median: X ms
After median: Y ms
Measured improvement: Z%
```

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

## CI/CD

GitHub Actions runs the `CI` workflow on pushes to `main` and pull requests targeting `main`. It installs the project from `pyproject.toml`, checks patch whitespace, and runs the normal unit and optimizer test suite without integration mode. A separate job starts PostgreSQL 16 as a service container, reuses the existing database initialization and fixtures, and runs the full PostgreSQL integration suite with `RUN_INTEGRATION_TESTS=1`.

The workflow fails when tests or repository checks fail. This milestone performs CI validation only; the repository does not yet contain a Dockerfile, so Docker image validation will be added after application Dockerization. No deployment, registry publishing, or production credentials are used.
