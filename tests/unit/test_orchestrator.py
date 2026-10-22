"""Unit tests for MultiAgentOrchestrator facade dispatching messages across agents."""

from unittest.mock import AsyncMock, MagicMock
import pytest

from asas.core.llm_client import LLMClient
from asas.modules.agents.orchestrator import MultiAgentOrchestrator
from asas.modules.agents.schemas import AgentResponse, AgentRole, SupervisorDecision
from asas.modules.memory.service import MemoryService
from asas.modules.tools.registry import ToolRegistry


@pytest.fixture
def mock_components():
    client = MagicMock(spec=LLMClient)
    registry = MagicMock(spec=ToolRegistry)
    memory = MagicMock(spec=MemoryService)
    return client, registry, memory


def test_orchestrator_initialization(mock_components):
    """Kiểm tra khởi tạo Orchestrator tự động lắp ráp 4 Agent chuyên trách."""
    client, registry, memory = mock_components
    orchestrator = MultiAgentOrchestrator(
        llm_client=client,
        tool_registry=registry,
        memory_service=memory,
    )
    assert orchestrator.supervisor.role == AgentRole.SUPERVISOR
    assert orchestrator.tutor.role == AgentRole.TUTOR
    assert orchestrator.evaluator.role == AgentRole.EVALUATOR
    assert orchestrator.planner.role == AgentRole.PLANNER


@pytest.mark.asyncio
async def test_orchestrator_dispatch_to_tutor(mock_components):
    """Kiểm tra luồng phân phối tin nhắn đến TutorAgent khi Supervisor ra quyết định."""
    client, registry, memory = mock_components
    orchestrator = MultiAgentOrchestrator(client, registry, memory)

    # Mock Supervisor quyết định gọi Tutor
    orchestrator.supervisor.route = AsyncMock(
        return_value=SupervisorDecision(
            next_agent=AgentRole.TUTOR,
            reasoning="Học sinh hỏi bài giải phương trình",
            instructions="Gợi ý từng bước",
        )
    )
    orchestrator.tutor.run = AsyncMock(
        return_value=AgentResponse(agent_role=AgentRole.TUTOR, content="Hãy thử đưa về dạng tích nhé!")
    )

    messages = [{"role": "user", "content": "Giải giúp em x^2 - 4 = 0"}]
    decision, response = await orchestrator.dispatch(messages=messages, student_id="st_01")

    assert decision.next_agent == AgentRole.TUTOR
    assert response.agent_role == AgentRole.TUTOR
    assert "dạng tích" in response.content
    orchestrator.tutor.run.assert_called_once_with(messages=messages, instructions="Gợi ý từng bước")


@pytest.mark.asyncio
async def test_orchestrator_dispatch_to_evaluator(mock_components):
    """Kiểm tra luồng phân phối tin nhắn đến EvaluatorAgent."""
    client, registry, memory = mock_components
    orchestrator = MultiAgentOrchestrator(client, registry, memory)

    orchestrator.supervisor.route = AsyncMock(
        return_value=SupervisorDecision(
            next_agent=AgentRole.EVALUATOR,
            reasoning="Học sinh gửi code nhờ chấm bài",
        )
    )
    orchestrator.evaluator.run = AsyncMock(
        return_value=AgentResponse(agent_role=AgentRole.EVALUATOR, content="Code thiếu kiểm tra trường hợp mảng rỗng.")
    )

    messages = [{"role": "user", "content": "Thầy xem giúp em đoạn code này"}]
    decision, response = await orchestrator.dispatch(messages=messages)

    assert decision.next_agent == AgentRole.EVALUATOR
    assert response.agent_role == AgentRole.EVALUATOR
    assert "mảng rỗng" in response.content
    orchestrator.evaluator.run.assert_called_once_with(messages=messages, instructions=None)


@pytest.mark.asyncio
async def test_orchestrator_dispatch_to_planner(mock_components):
    """Kiểm tra luồng phân phối tin nhắn đến PlannerAgent kèm mã học sinh."""
    client, registry, memory = mock_components
    orchestrator = MultiAgentOrchestrator(client, registry, memory)

    orchestrator.supervisor.route = AsyncMock(
        return_value=SupervisorDecision(
            next_agent=AgentRole.PLANNER,
            reasoning="Học sinh muốn lên kế hoạch học tập",
        )
    )
    orchestrator.planner.run = AsyncMock(
        return_value=AgentResponse(agent_role=AgentRole.PLANNER, content="Lộ trình 3 ngày cho bạn...")
    )

    messages = [{"role": "user", "content": "Em nên học gì tuần tới?"}]
    decision, response = await orchestrator.dispatch(messages=messages, student_id="st_01")

    assert decision.next_agent == AgentRole.PLANNER
    assert response.agent_role == AgentRole.PLANNER
    orchestrator.planner.run.assert_called_once_with(messages=messages, student_id="st_01", instructions=None)
