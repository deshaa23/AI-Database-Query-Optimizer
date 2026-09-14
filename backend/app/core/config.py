"""Application configuration."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables or a local .env file."""

    app_name: str = "AI Database Query Optimizer"
    app_environment: str = "development"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    frontend_origin: str = "http://localhost:5173"
    postgres_db: str = "query_optimizer"
    postgres_user: str = "query_optimizer"
    postgres_password: str = ""
    postgres_host: str = "127.0.0.1"
    postgres_port: int = 5432
    ai_provider: str = ""
    ai_model: str = ""
    openai_api_key: str = ""
    benchmark_timeout_ms: int = 30000
    benchmark_repetitions: int = 5
    benchmark_warmup_runs: int = 1
    benchmark_min_improvement_percent: float = 5.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings."""

    return Settings()
