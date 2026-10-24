"""Unit tests for TutorAgent with Socratic guidance and tool calling capability."""

from unittest.mock import AsyncMock, MagicMock
import pytest

from asas.core.llm_client import LLMClient
from asas.modules.agents.schemas import AgentRole
from asas.modules.agents.tutor import TutorAgent
from asas.modules.tools.registry import ToolRegistry


@pytest.fixture
def mock_llm_client():
    client = MagicMock(spec=LLMClient)
    client.chat_with_tools = AsyncMock(return_value="Để giải bài toán này, trước hết bạn hãy cho tôi biết: Đạo hàm của x^2 là gì?")
    return client


@pytest.fixture
def mock_registry():
    registry = MagicMock(spec=ToolRegistry)
    registry.get_openai_tools.return_value = [{"type": "function", "function": {"name": "calculator"}}]
    return registry


def test_tutor_agent_initialization(mock_llm_client, mock_registry):
    """Kiểm tra khởi tạo TutorAgent đúng vai trò và cấu hình."""
    tutor = TutorAgent(llm_client=mock_llm_client, tool_registry=mock_registry)
    assert tutor.role == AgentRole.TUTOR
    assert "Socratic" in tutor.system_prompt or "gợi mở" in tutor.system_prompt


@pytest.mark.asyncio
async def test_tutor_agent_run_success(mock_llm_client, mock_registry):
    """Kiểm tra TutorAgent điều phối tin nhắn qua chat_with_tools và đóng gói AgentResponse."""
    tutor = TutorAgent(llm_client=mock_llm_client, tool_registry=mock_registry)

    messages = [{"role": "user", "content": "Hãy giải giúp tôi phương trình x^2 - 4 = 0"}]
    response = await tutor.run(messages=messages)

    assert response.agent_role == AgentRole.TUTOR
    assert "Đạo hàm" in response.content or "x^2" in response.content
    assert mock_llm_client.chat_with_tools.called

    # Kiểm tra tin nhắn gửi đến LLM có chứa System Prompt Socratic
    called_messages = mock_llm_client.chat_with_tools.call_args.kwargs["messages"]
    assert called_messages[0]["role"] == "system"
    assert called_messages[-1]["content"] == "Hãy giải giúp tôi phương trình x^2 - 4 = 0"


@pytest.mark.asyncio
async def test_tutor_agent_with_supervisor_instructions(mock_llm_client, mock_registry):
    """Kiểm tra TutorAgent tích hợp chỉ đạo bổ sung từ Supervisor vào ngữ cảnh."""
    tutor = TutorAgent(llm_client=mock_llm_client, tool_registry=mock_registry)

    messages = [{"role": "user", "content": "Em chưa hiểu thuật toán QuickSort."}]
    instructions = "Học sinh này thích hình ảnh trực quan, hãy lấy ví dụ xếp hàng học sinh."

    response = await tutor.run(messages=messages, instructions=instructions)

    assert response.agent_role == AgentRole.TUTOR
    called_messages = mock_llm_client.chat_with_tools.call_args.kwargs["messages"]
    system_content = called_messages[0]["content"]
    assert "xếp hàng học sinh" in system_content
