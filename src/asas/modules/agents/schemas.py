"""Pydantic schemas and decision models for the Multi-Agent Orchestration System."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field, field_validator
from asas.modules.memory.schemas import utc_now


class AgentRole(str, Enum):
    """Vai trò của từng tác tử chuyên trách trong hệ thống ASAS."""

    SUPERVISOR = "supervisor"
    TUTOR = "tutor"
    EVALUATOR = "evaluator"
    PLANNER = "planner"


class SupervisorDecision(BaseModel):
    """Cấu trúc quyết định phân luồng từ Supervisor Agent sang Agent chuyên trách."""

    next_agent: AgentRole = Field(
        ...,
        description="Agent tiếp theo được ủy quyền xử lý (tutor, evaluator, hoặc planner).",
    )
    reasoning: str = Field(
        ...,
        description="Lý giải nguyên nhân tại sao yêu cầu của học sinh nên được chuyển cho agent này.",
    )
    instructions: Optional[str] = Field(
        default=None,
        description="Chỉ đạo hoặc lưu ý sư phạm bổ sung của Supervisor gửi cho agent tiếp nhận.",
    )

    @field_validator("next_agent")
    @classmethod
    def validate_not_supervisor(cls, v: AgentRole) -> AgentRole:
        """Ngăn chặn Supervisor tự gọi lại chính mình gây vòng lặp vô tận."""
        if v == AgentRole.SUPERVISOR:
            raise ValueError("Supervisor không thể tự điều hướng lại chính mình.")
        return v


class AgentResponse(BaseModel):
    """Phản hồi hoàn chỉnh từ một tác tử sau khi xử lý xong yêu cầu."""

    agent_role: AgentRole
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
