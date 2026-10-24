from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from pydantic import BaseModel, Field

from asas.core.config import Settings
from asas.core.llm_client import LLMClient
from asas.modules.tools.base import BaseTool, ToolResult
from asas.modules.tools.registry import ToolRegistry


class AddArgs(BaseModel):
    a: int = Field(default=0, description="Số thứ nhất")
    b: int = Field(default=0, description="Số thứ hai")


class AddTool(BaseTool):
    name = "add_numbers"
    description = "Cộng hai số nguyên a và b"
    args_schema = AddArgs

    async def execute(self, a: int = 0, b: int = 0, **kwargs) -> ToolResult:
        return ToolResult(success=True, output=str(a + b))


@pytest.fixture
def dummy_settings():
    return Settings(
        nvidia_api_key="nvapi-test-key",
        nvidia_base_url="https://integrate.api.nvidia.com/v1",
        default_model="deepseek-ai/deepseek-v4.1-flash",
    )


@pytest.fixture
def tool_registry():
    reg = ToolRegistry()
    reg.register_tool(AddTool())
    return reg


@pytest.mark.asyncio
async def test_chat_with_tools_direct_answer_no_tool_called(dummy_settings, tool_registry):
    """Kiểm tra khi LLM không cần dùng tool và trả lời trực tiếp cho người dùng."""
    client = LLMClient(settings=dummy_settings)

    mock_msg = MagicMock()
    mock_msg.tool_calls = None
    mock_msg.content = "Xin chào! Tôi có thể giúp gì cho việc học của bạn?"
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=mock_msg)]

    with patch.object(client.client.chat.completions, "create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_response

        messages = [{"role": "user", "content": "Chào bạn"}]
        answer = await client.chat_with_tools(messages=messages, tool_registry=tool_registry)

        assert answer == "Xin chào! Tôi có thể giúp gì cho việc học của bạn?"
        assert mock_create.await_count == 1


@pytest.mark.asyncio
async def test_chat_with_tools_single_tool_loop(dummy_settings, tool_registry):
    """Kiểm tra vòng lặp: Model yêu cầu gọi tool -> Thực thi tool -> Trả kết quả -> Model chốt đáp án."""
    client = LLMClient(settings=dummy_settings)

    # Lượt 1: LLM yêu cầu gọi add_numbers(a=15, b=25)
    tool_call_mock = MagicMock()
    tool_call_mock.id = "call_abc123"
    tool_call_mock.type = "function"
    tool_call_mock.function.name = "add_numbers"
    tool_call_mock.function.arguments = '{"a": 15, "b": 25}'

    turn1_msg = MagicMock()
    turn1_msg.tool_calls = [tool_call_mock]
    turn1_msg.content = None
    turn1_resp = MagicMock(choices=[MagicMock(message=turn1_msg)])

    # Lượt 2: LLM nhận kết quả 40 và trả lời cuối cùng
    turn2_msg = MagicMock()
    turn2_msg.tool_calls = None
    turn2_msg.content = "Tổng của 15 và 25 là 40."
    turn2_resp = MagicMock(choices=[MagicMock(message=turn2_msg)])

    with patch.object(client.client.chat.completions, "create", new_callable=AsyncMock) as mock_create:
        mock_create.side_effect = [turn1_resp, turn2_resp]

        messages = [{"role": "user", "content": "Tính 15 + 25 giúp tôi"}]
        answer = await client.chat_with_tools(messages=messages, tool_registry=tool_registry)

        assert answer == "Tổng của 15 và 25 là 40."
        assert mock_create.await_count == 2

        # Kiểm tra lượt gọi thứ 2 đã được nạp kết quả tool vào messages
        second_call_messages = mock_create.call_args_list[1].kwargs["messages"]
        tool_messages = [m for m in second_call_messages if m.get("role") == "tool"]
        assert len(tool_messages) == 1
        assert tool_messages[0]["tool_call_id"] == "call_abc123"
        assert tool_messages[0]["content"] == "40"
