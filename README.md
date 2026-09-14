# AI Database Query Optimizer

AI Database Query Optimizer is a portfolio project for analyzing SQL queries and PostgreSQL execution plans, recommending performance improvements, and validating recommendations through measured benchmarks.

## Current functionality

Milestone 1 provides a small FastAPI backend foundation with:

- Environment-based application settings using `pydantic-settings`
- `GET /api/v1/health`, which confirms that the application is running
- A pytest test for the health endpoint

PostgreSQL, SQL parsing, optimization recommendations, benchmarking, AI components, and the frontend will be added in later milestones.

## Requirements

- Python 3.11 or newer

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

Optionally copy `.env.example` to `.env` and adjust the application settings. `.env` is ignored by Git and must not contain committed secrets.

## Run the application

```powershell
uvicorn app.main:app --app-dir backend --reload
```

The health endpoint is available at <http://127.0.0.1:8000/api/v1/health>.

## Run tests

```powershell
python -m pytest
```
