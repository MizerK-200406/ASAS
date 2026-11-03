from functools import lru_cache
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    nvidia_api_key: str
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    default_model: str = "deepseek-ai/deepseek-v4.1-flash"
    app_env: Literal["development", "production", "testing"] = "development"
    log_level: str = "INFO"
    database_url: str = "postgresql://postgres:8ijb9okn0plm@localhost:5432/asas_db"
    test_database_url: str = "postgresql://postgres:8ijb9okn0plm@localhost:5432/asas_test_db"


@lru_cache()
def get_settings() -> Settings:
    """Return a cached singleton instance of Settings."""
    return Settings()  # type: ignore[call-arg]
