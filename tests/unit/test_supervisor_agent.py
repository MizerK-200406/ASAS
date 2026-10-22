"""Unit tests for SupervisorAgent orchestrating intent routing to specialized agents."""

from unittest.mock import AsyncMock, MagicMock
import pytest

from asas.core.llm_client import LLMClient, LLMClientError
from asas.modules.agents.schemas import AgentRole, SupervisorDecision
from asas.modules.agents.supervisor import SupervisorAgent


@pytest.fixture
def mock_llm_client():
    client = MagicMock(spec=LLMClient)
    return client


def test_supervisor_initialization(mock_llm_client):
    """Kiểm tra khởi tạo SupervisorAgent đúng vai trò và system prompt điều phối."""
    supervisor = SupervisorAgent(llm_client=mock_llm_client)
    assert supervisor.role == AgentRole.SUPERVISOR
    assert "phân loại" in supervisor.system_prompt or "điều phối" in supervisor.system_prompt or "tutor" in supervisor.system_prompt


@pytest.mark.asyncio
async def test_supervisor_routes_to_tutor(mock_llm_client):
    """Kiểm tra câu hỏi kiến thức/hướng dẫn giải được phân loại sang TutorAgent."""
    mock_llm_client.structured_output = AsyncMock(
        return_value=SupervisorDecision(
            next_agent=AgentRole.TUTOR,
            reasoning="Học sinh muốn tìm hiểu về thuật toán Sắp xếp nổi bọt (Bubble Sort)",
            instructions="Gợi ý bằng cách so sánh 2 phần tử liền kề",
        )
    )
    supervisor = SupervisorAgent(llm_client=mock_llm_client)

    messages = [{"role": "user", "content": "Thuật toán Bubble Sort hoạt động thế nào ạ?"}]
    decision = await supervisor.route(messages=messages)

    assert decision.next_agent == AgentRole.TUTOR
    assert "Bubble Sort" in decision.reasoning
    assert mock_llm_client.structured_output.called


@pytest.mark.asyncio
async def test_supervisor_routes_to_evaluator(mock_llm_client):
    """Kiểm tra yêu cầu chấm bài hoặc phản biện code được phân loại sang EvaluatorAgent."""
    mock_llm_client.structured_output = AsyncMock(
        return_value=SupervisorDecision(
            next_agent=AgentRole.EVALUATOR,
            reasoning="Học sinh gửi đoạn code nhờ tìm lỗi sai",
            instructions="Kiểm tra kỹ các trường hợp mảng rỗng",
        )
    )
    supervisor = SupervisorAgent(llm_client=mock_llm_client)

    messages = [{"role": "user", "content": "Thầy chấm giúp em đoạn code này xem có lỗi gì không ạ."}]
    decision = await supervisor.route(messages=messages)

    assert decision.next_agent == AgentRole.EVALUATOR
    assert decision.instructions == "Kiểm tra kỹ các trường hợp mảng rỗng"


@pytest.mark.asyncio
async def test_supervisor_routes_to_planner(mock_llm_client):
    """Kiểm tra câu hỏi về kế hoạch hoặc thời gian biểu được phân loại sang PlannerAgent."""
    mock_llm_client.structured_output = AsyncMock(
        return_value=SupervisorDecision(
            next_agent=AgentRole.PLANNER,
            reasoning="Học sinh hỏi về lộ trình ôn thi tuần tới",
        )
    )
    supervisor = SupervisorAgent(llm_client=mock_llm_client)

    messages = [{"role": "user", "content": "Em nên học gì trong 3 ngày tới để cải thiện điểm số?"}]
    decision = await supervisor.route(messages=messages)

    assert decision.next_agent == AgentRole.PLANNER


@pytest.mark.asyncio
async def test_supervisor_fallback_on_llm_error(mock_llm_client):
    """Khi LLM gặp lỗi parse, Supervisor fallback an toàn về TUTOR thay vì làm gián đoạn trò chuyện."""
    mock_llm_client.structured_output = AsyncMock(side_effect=LLMClientError("Parse JSON failed"))
    supervisor = SupervisorAgent(llm_client=mock_llm_client)

    messages = [{"role": "user", "content": "Một câu hỏi bất kỳ"}]
    decision = await supervisor.route(messages=messages)

    assert decision.next_agent == AgentRole.TUTOR
    assert "Fallback" in decision.reasoning
