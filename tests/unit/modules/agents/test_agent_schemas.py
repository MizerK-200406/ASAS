"""Unit tests for Evaluator Agent schemas."""

from datetime import datetime
import pytest
from pydantic import ValidationError

from asas.modules.agents.schemas import (
    AgentResponse,
    AgentRole,
    EvaluationResult,
)


def test_agent_role_enum():
    """Kiểm tra các giá trị hợp lệ của AgentRole."""
    assert AgentRole.EVALUATOR == "evaluator"


def test_evaluation_result_schema_valid():
    """Kiểm tra EvaluationResult khởi tạo thành công với cấu trúc chuẩn."""
    result = EvaluationResult(
        score_summary="Đạt 80%",
        strengths=["Nắm vững cú pháp cơ bản", "Hiểu cấu trúc mảng"],
        knowledge_gaps=["Chưa hiểu rõ đệ quy", "Sai điều kiện dừng"],
        critique="Học sinh bị tràn ngăn xếp do thiếu điều kiện dừng ở hàm recursive.",
        recommendations=["Ôn tập lại base case của hàm đệ quy", "Làm thêm 3 bài tập về Fibonacci"],
        improvement_plan="Bước 1: Đọc lại lý thuyết. Bước 2: Thực hành debug.",
    )
    assert result.score_summary == "Đạt 80%"
    assert len(result.strengths) == 2
    assert len(result.knowledge_gaps) == 2
    assert "tràn ngăn xếp" in result.critique
    assert len(result.recommendations) == 2
    assert result.improvement_plan is not None


def test_evaluation_result_requires_critique():
    """Kiểm tra EvaluationResult bắt buộc phải có critique."""
    with pytest.raises(ValidationError):
        EvaluationResult(
            strengths=["Tốt"],
            knowledge_gaps=[],
        )


def test_agent_response_schema():
    """Kiểm tra AgentResponse chứa đầy đủ thông tin phản hồi từ Evaluator Agent."""
    eval_res = EvaluationResult(
        critique="Lời giải cần tối ưu thời gian.",
        knowledge_gaps=["Độ phức tạp O(N^2)"],
    )
    resp = AgentResponse(
        agent_role=AgentRole.EVALUATOR,
        evaluation=eval_res,
        content="Đã hoàn thành đánh giá bài làm.",
        metadata={"model": "deepseek"},
    )
    assert resp.agent_role == AgentRole.EVALUATOR
    assert resp.evaluation.critique == "Lời giải cần tối ưu thời gian."
    assert resp.metadata["model"] == "deepseek"
    assert isinstance(resp.created_at, datetime)
