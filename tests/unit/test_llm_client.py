import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from pydantic import BaseModel

from asas.core.config import Settings
from asas.core.llm_client import LLMClient, LLMClientError, LLMParseError


class SampleSchema(BaseModel):
    name: str
    score: int


@pytest.fixture
def dummy_settings():
    return Settings(
        nvidia_api_key="nvapi-dummy-key",
        nvidia_base_url="https://integrate.api.nvidia.com/v1",
        default_model="deepseek-ai/deepseek-v4-flash",
    )


def test_llm_client_initialization(dummy_settings):
    """Test client initializes with custom or default settings."""
    client = LLMClient(settings=dummy_settings)
    assert client.settings.nvidia_api_key == "nvapi-dummy-key"
    assert client.client is not None


@pytest.mark.asyncio
async def test_chat_completion_success(dummy_settings):
    """Test standard chat completion returning raw text."""
    client = LLMClient(settings=dummy_settings)

    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "Xin chào, tôi là AI Study Assistant!"
    mock_response.choices = [mock_choice]

    with patch.object(
        client.client.chat.completions, "create", new_callable=AsyncMock
    ) as mock_create:
        mock_create.return_value = mock_response

        messages = [{"role": "user", "content": "Chào bạn"}]
        result = await client.chat_completion(messages=messages)

        assert result == "Xin chào, tôi là AI Study Assistant!"
        mock_create.assert_awaited_once()


@pytest.mark.asyncio
async def test_structured_output_success(dummy_settings):
    """Test structured output parsing valid JSON into Pydantic model."""
    client = LLMClient(settings=dummy_settings)

    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = json.dumps({"name": "Math Quiz", "score": 100})
    mock_response.choices = [mock_choice]

    with patch.object(
        client.client.chat.completions, "create", new_callable=AsyncMock
    ) as mock_create:
        mock_create.return_value = mock_response

        messages = [{"role": "user", "content": "Tạo dữ liệu mẫu"}]
        result = await client.structured_output(
            messages=messages,
            response_model=SampleSchema,
        )

        assert isinstance(result, SampleSchema)
        assert result.name == "Math Quiz"
        assert result.score == 100


@pytest.mark.asyncio
async def test_structured_output_cleans_markdown_fences(dummy_settings):
    """Test structured output strips ```json ... ``` markdown wrappers."""
    client = LLMClient(settings=dummy_settings)

    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "```json\n{\"name\": \"Physics Quiz\", \"score\": 90}\n```"
    mock_response.choices = [mock_choice]

    with patch.object(
        client.client.chat.completions, "create", new_callable=AsyncMock
    ) as mock_create:
        mock_create.return_value = mock_response

        messages = [{"role": "user", "content": "Tạo dữ liệu mẫu"}]
        result = await client.structured_output(
            messages=messages,
            response_model=SampleSchema,
        )

        assert result.name == "Physics Quiz"
        assert result.score == 90


@pytest.mark.asyncio
async def test_structured_output_invalid_json_raises_error(dummy_settings):
    """Test that invalid JSON raises LLMParseError."""
    client = LLMClient(settings=dummy_settings)

    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "Đây là văn bản bình thường không phải JSON"
    mock_response.choices = [mock_choice]

    with patch.object(
        client.client.chat.completions, "create", new_callable=AsyncMock
    ) as mock_create:
        mock_create.return_value = mock_response

        messages = [{"role": "user", "content": "Tạo dữ liệu"}]
        with pytest.raises(LLMParseError):
            await client.structured_output(
                messages=messages,
                response_model=SampleSchema,
            )
