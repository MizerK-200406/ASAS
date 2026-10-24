import os
import pytest
from pydantic import ValidationError

from asas.core.config import Settings, get_settings


def test_settings_default_values(monkeypatch):
    """Test that default values are set correctly when API key is provided."""
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test-key-12345")
    # Clear other env vars if set
    monkeypatch.delenv("NVIDIA_BASE_URL", raising=False)
    monkeypatch.delenv("DEFAULT_MODEL", raising=False)

    settings = Settings()
    assert settings.nvidia_api_key == "nvapi-test-key-12345"
    assert settings.nvidia_base_url == "https://integrate.api.nvidia.com/v1"
    assert settings.default_model == "deepseek-ai/deepseek-v4.1-flash"
    assert settings.app_env == "development"
    assert settings.log_level == "INFO"


def test_settings_missing_api_key(monkeypatch):
    """Test that missing required NVIDIA_API_KEY raises ValidationError."""
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_get_settings_caching(monkeypatch):
    """Test that get_settings() returns a cached instance."""
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-cached-key")
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2
