"""Unit tests for Multi-Agent schemas and decision models."""

from datetime import datetime
import pytest
from pydantic import ValidationError

from asas.modules.agents.schemas import (
    AgentResponse,
    AgentRole,
    SupervisorDecision,
)


def test_agent_role_enum():
    """Kiểm tra các giá trị hợp lệ của AgentRole."""
    assert AgentRole.SUPERVISOR == "supervisor"
    assert AgentRole.TUTOR == "tutor"
    assert AgentRole.EVALUATOR == "evaluator"
    assert AgentRole.PLANNER == "planner"


def test_supervisor_decision_schema_valid():
    """Kiểm tra SupervisorDecision khởi tạo thành công với cấu trúc chuẩn."""
    decision = SupervisorDecision(
        next_agent=AgentRole.TUTOR,
        reasoning="Học sinh đang hỏi giải thích khái niệm Binary Search",
        instructions="Hãy giải thích từng bước theo phương pháp gợi mở Socratic",
    )
    assert decision.next_agent == AgentRole.TUTOR
    assert "Socratic" in decision.instructions


def test_supervisor_decision_cannot_route_to_supervisor():
    """Supervisor không được phép tự điều hướng lại về chính mình để tránh đệ quy."""
    with pytest.raises(ValidationError):
        SupervisorDecision(
            next_agent=AgentRole.SUPERVISOR,
            reasoning="Tự gọi lại",
        )


def test_agent_response_schema():
    """Kiểm tra AgentResponse chứa đầy đủ thông tin phản hồi từ tác tử chuyên trách."""
    resp = AgentResponse(
        agent_role=AgentRole.EVALUATOR,
        content="Bài làm của bạn có 1 lỗi logic ở dòng 5.",
        metadata={"issues_found": 1},
    )
    assert resp.agent_role == AgentRole.EVALUATOR
    assert resp.metadata["issues_found"] == 1
    assert isinstance(resp.created_at, datetime)
