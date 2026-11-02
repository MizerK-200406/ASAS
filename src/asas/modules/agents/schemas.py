"""Pydantic schemas for the AI Evaluator Agent system."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from asas.modules.memory.schemas import utc_now


class AgentRole(str, Enum):
    """Vai trò của tác tử trong hệ thống."""

    EVALUATOR = "evaluator"


class EvaluationResult(BaseModel):
    """Kết quả đánh giá sư phạm chuẩn hóa của Evaluator Agent."""

    score_summary: Optional[str] = Field(None, description="Tóm tắt điểm số hoặc đánh giá tổng quan ngắn gọn")
    strengths: List[str] = Field(
        default_factory=list,
        description="Điểm mạnh, các câu hỏi hoặc khái niệm học sinh đã nắm vững",
    )
    knowledge_gaps: List[str] = Field(
        default_factory=list,
        description="Lỗ hổng kiến thức, ngộ nhận lý thuyết hoặc sai sót logic phát hiện được",
    )
    critique: str = Field(
        ...,
        description="Phân tích sư phạm chi tiết về các lỗi sai và nguyên nhân",
    )
    recommendations: List[str] = Field(
        default_factory=list,
        description="Danh sách lời khuyên và chủ đề cần tập trung ôn luyện",
    )
    improvement_plan: Optional[str] = Field(
        None,
        description="Kế hoạch hành động cụ thể để khắc phục lỗ hổng kiến thức",
    )


class AgentResponse(BaseModel):
    """Phản hồi hoàn chỉnh từ Evaluator Agent."""

    agent_role: AgentRole = AgentRole.EVALUATOR
    evaluation: EvaluationResult
    content: str = Field(default="", description="Nội dung tổng hợp hoặc hiển thị dạng văn bản")
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
