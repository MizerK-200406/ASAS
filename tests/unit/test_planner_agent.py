"""Unit tests for PlannerAgent generating personalized learning roadmaps from memory."""

from unittest.mock import AsyncMock, MagicMock
import pytest

from asas.core.llm_client import LLMClient
from asas.modules.agents.planner import PlannerAgent
from asas.modules.agents.schemas import AgentRole
from asas.modules.memory.schemas import StudentProfile, QuizRecord, FlashcardProgress
from asas.modules.memory.service import MemoryService


@pytest.fixture
def mock_llm_client():
    client = MagicMock(spec=LLMClient)
    client.chat_completion = AsyncMock(
        return_value=(
            "### LỘ TRÌNH ÔN TẬP 3 NGÀY CHO NGUYỄN VĂN A:\n"
            "- Ngày 1: Ôn lại Giải tích vì điểm Quiz gần đây là 50%.\n"
            "- Ngày 2: Hoàn thành 5 thẻ Flashcard đến hạn ôn tập.\n"
            "- Ngày 3: Làm bài kiểm tra tổng hợp."
        )
    )
    return client


@pytest.fixture
def mock_memory_service():
    service = MagicMock(spec=MemoryService)
    service.get_student_summary = AsyncMock(
        return_value={
            "profile": StudentProfile(student_id="st_01", name="Nguyễn Văn A"),
            "quiz_stats": {"total_quizzes": 3, "average_score": 65.0, "total_correct": 13, "total_questions": 20},
            "recent_quizzes": [
                QuizRecord(student_id="st_01", topic="Giải tích", score_percentage=50.0, total_questions=5, correct_count=2),
                QuizRecord(student_id="st_01", topic="Hình học", score_percentage=80.0, total_questions=5, correct_count=4),
            ],
        }
    )
    service.get_due_flashcards = AsyncMock(
        return_value=[
            FlashcardProgress(card_id="c1", student_id="st_01", front="Công thức đạo hàm", back="f'(x)"),
        ]
    )
    return service


def test_planner_agent_initialization(mock_llm_client):
    """Kiểm tra khởi tạo PlannerAgent đúng vai trò PLANNER và system prompt định hướng lộ trình."""
    planner = PlannerAgent(llm_client=mock_llm_client)
    assert planner.role == AgentRole.PLANNER
    assert "lộ trình" in planner.system_prompt or "Planner" in planner.system_prompt or "kế hoạch" in planner.system_prompt


@pytest.mark.asyncio
async def test_planner_agent_run_without_memory(mock_llm_client):
    """Kiểm tra PlannerAgent lên kế hoạch cơ bản khi chưa có dữ liệu bộ nhớ học sinh."""
    planner = PlannerAgent(llm_client=mock_llm_client)
    messages = [{"role": "user", "content": "Em muốn ôn thi vào lớp 10 môn Toán trong 1 tuần."}]

    response = await planner.run(messages=messages)

    assert response.agent_role == AgentRole.PLANNER
    assert mock_llm_client.chat_completion.called
    assert response.metadata["has_memory_context"] is False


@pytest.mark.asyncio
async def test_planner_agent_run_with_memory_context(mock_llm_client, mock_memory_service):
    """Kiểm tra PlannerAgent tích hợp dữ liệu điểm yếu và thẻ ôn tập từ MemoryService."""
    planner = PlannerAgent(llm_client=mock_llm_client, memory_service=mock_memory_service)
    messages = [{"role": "user", "content": "Thầy hãy lên kế hoạch học tập giúp em."}]

    response = await planner.run(messages=messages, student_id="st_01")

    assert response.agent_role == AgentRole.PLANNER
    assert response.metadata["has_memory_context"] is True
    assert mock_memory_service.get_student_summary.called
    assert mock_memory_service.get_due_flashcards.called

    # Kiểm tra ngữ cảnh gửi tới LLM có chứa dữ liệu thực tế của học sinh
    called_messages = mock_llm_client.chat_completion.call_args.kwargs["messages"]
    system_text = called_messages[0]["content"]
    assert "Nguyễn Văn A" in system_text
    assert "Giải tích" in system_text
    assert "65.0%" in system_text
