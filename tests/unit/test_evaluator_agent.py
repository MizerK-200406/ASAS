"""Unit tests for EvaluatorAgent performing critique, grading, and logic evaluation."""

from unittest.mock import AsyncMock, MagicMock
import pytest

from asas.core.llm_client import LLMClient
from asas.modules.agents.evaluator import EvaluatorAgent
from asas.modules.agents.schemas import AgentRole


@pytest.fixture
def mock_llm_client():
    client = MagicMock(spec=LLMClient)
    client.chat_completion = AsyncMock(
        return_value=(
            "### ĐÁNH GIÁ BÀI LÀM:\n"
            "1. Điểm mạnh: Cú pháp hàm viết đúng chuẩn PEP8.\n"
            "2. Lỗi logic: Dòng 4 chưa xử lý trường hợp n = 0, gây ra ZeroDivisionError.\n"
            "3. Hướng khắc phục: Thêm điều kiện if n == 0: return 0."
        )
    )
    return client


def test_evaluator_agent_initialization(mock_llm_client):
    """Kiểm tra khởi tạo EvaluatorAgent đúng vai trò và system prompt chuẩn phản biện."""
    evaluator = EvaluatorAgent(llm_client=mock_llm_client)
    assert evaluator.role == AgentRole.EVALUATOR
    assert "chấm bài" in evaluator.system_prompt or "phản biện" in evaluator.system_prompt or "Evaluator" in evaluator.system_prompt


@pytest.mark.asyncio
async def test_evaluator_agent_run_success(mock_llm_client):
    """Kiểm tra EvaluatorAgent tiếp nhận bài làm của học sinh và trả về AgentResponse chi tiết."""
    evaluator = EvaluatorAgent(llm_client=mock_llm_client)

    student_submission = [
        {
            "role": "user",
            "content": "Nhờ thầy chấm giúp em đoạn code tính trung bình cộng:\ndef avg(nums):\n    return sum(nums) / len(nums)",
        }
    ]

    response = await evaluator.run(messages=student_submission)

    assert response.agent_role == AgentRole.EVALUATOR
    assert "ZeroDivisionError" in response.content
    assert mock_llm_client.chat_completion.called

    # Kiểm tra system prompt gửi tới LLM mang tính chất đánh giá
    called_messages = mock_llm_client.chat_completion.call_args.kwargs["messages"]
    assert called_messages[0]["role"] == "system"
    assert "chấm bài" in called_messages[0]["content"] or "phản biện" in called_messages[0]["content"]


@pytest.mark.asyncio
async def test_evaluator_agent_with_supervisor_instructions(mock_llm_client):
    """Kiểm tra EvaluatorAgent tích hợp tiêu chí chấm điểm đặc biệt từ Supervisor."""
    evaluator = EvaluatorAgent(llm_client=mock_llm_client)

    messages = [{"role": "user", "content": "Em vừa viết xong bài luận ngắn về hiện tượng Quang hợp."}]
    instructions = "Hãy chấm điểm khắt khe về tính chính xác của phương trình hóa học và cho điểm thang 10."

    response = await evaluator.run(messages=messages, instructions=instructions)

    assert response.agent_role == AgentRole.EVALUATOR
    called_messages = mock_llm_client.chat_completion.call_args.kwargs["messages"]
    assert "thang 10" in called_messages[0]["content"]
