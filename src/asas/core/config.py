from functools import lru_cache
from typing import Literal
from pydantic import model_validator
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
    default_model: str = "poolside/laguna-xs-2.1"
    generator_model: str = "poolside/laguna-xs-2.1"
    evaluator_model: str = "poolside/laguna-xs-2.1"
    app_env: Literal["development", "production", "testing"] = "development"
    log_level: str = "INFO"
    database_url: str = "postgresql://postgres:8ijb9okn0plm@localhost:5432/asas_db"
    test_database_url: str = "postgresql://postgres:8ijb9okn0plm@localhost:5432/asas_test_db"

    @model_validator(mode="after")
    def validate_working_model(self) -> "Settings":
        # Tự động thay thế các model cũ bị timeout (>3 phút) hoặc deprecated trên catalog NVIDIA
        slow_or_broken_models = {
            "deepseek-ai/deepseek-v4.1-flash",
            "nvidia/nemotron-3.5-bolt-e4b",
        }
        if self.default_model in slow_or_broken_models:
            self.default_model = "poolside/laguna-xs-2.1"
        if self.generator_model in slow_or_broken_models:
            self.generator_model = "poolside/laguna-xs-2.1"
        if self.evaluator_model in slow_or_broken_models:
            self.evaluator_model = "poolside/laguna-xs-2.1"
        return self


@lru_cache()
def get_settings() -> Settings:
    """Return a cached singleton instance of Settings."""
    return Settings()  # type: ignore[call-arg]
