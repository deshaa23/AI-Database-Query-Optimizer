"""Application configuration."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables or a local .env file."""

    app_name: str = "AI Database Query Optimizer"
    app_environment: str = "development"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    postgres_db: str = "query_optimizer"
    postgres_user: str = "query_optimizer"
    postgres_password: str = ""
    postgres_host: str = "127.0.0.1"
    postgres_port: int = 5432

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings."""

    return Settings()
