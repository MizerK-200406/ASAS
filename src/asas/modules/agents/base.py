"""Lớp cơ sở (Base Class) cho tất cả các AI Agents trong hệ thống ASAS."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from loguru import logger

from asas.core.llm_client import LLMClient
from asas.core.tools import Tool, ToolRegistry
from asas.modules.agents.schemas import AgentRole


class BaseAgent(ABC):
    """Lớp cơ sở trừu tượng chuẩn hóa cấu trúc của một AI Agent trong ASAS.

    Quản lý:
    - Vai trò sư phạm (AgentRole) và Persona/System Prompt.
    - LLMClient và mô hình chỉ định (model decoupling).
    - ToolRegistry (đăng ký và thực thi công cụ dự phòng cho tương lai).
    """

    def __init__(
        self,
        role: AgentRole,
        system_prompt: str,
        llm_client: Optional[LLMClient] = None,
        model: Optional[str] = None,
        tools: Optional[List[Tool]] = None,
    ) -> None:
        self.role = role
        self.system_prompt = system_prompt
        self.llm_client = llm_client or LLMClient()
        self.model = model
        self.tool_registry = ToolRegistry()

        if tools:
            for t in tools:
                self.register_tool(t)

    def register_tool(self, tool: Tool) -> None:
        """Đăng ký một công cụ cho Agent."""
        self.tool_registry.register(tool)
        logger.debug(f"[{self.role.value}] Đã đăng ký công cụ: {tool.name}")

    def get_target_model(self) -> str:
        """Lấy tên mô hình chỉ định hoặc mặc định từ settings."""
        if self.model:
            return self.model
        settings = getattr(self.llm_client, "settings", None)
        if not settings:
            return "poolside/laguna-xs-2.1"

        if self.role == AgentRole.GENERATOR:
            return getattr(settings, "generator_model", settings.default_model)
        elif self.role == AgentRole.EVALUATOR:
            return getattr(settings, "evaluator_model", settings.default_model)
        return settings.default_model

    @abstractmethod
    async def run(
        self,
        messages: List[Dict[str, Any]],
        instructions: Optional[str] = None,
    ) -> Any:
        """Thực thi tác tử với ngữ cảnh hội thoại hoặc chỉ dẫn bổ sung."""
        pass
