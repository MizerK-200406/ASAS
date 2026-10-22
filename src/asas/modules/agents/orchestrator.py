"""MultiAgentOrchestrator facade unifying Supervisor, Tutor, Evaluator, and Planner agents."""

from typing import Any, Dict, List, Optional, Tuple
from loguru import logger

from asas.core.llm_client import LLMClient
from asas.modules.agents.evaluator import EvaluatorAgent
from asas.modules.agents.planner import PlannerAgent
from asas.modules.agents.schemas import AgentResponse, AgentRole, SupervisorDecision
from asas.modules.agents.supervisor import SupervisorAgent
from asas.modules.agents.tutor import TutorAgent
from asas.modules.memory.service import MemoryService
from asas.modules.tools.registry import ToolRegistry, create_default_registry


class MultiAgentOrchestrator:
    """Facade điều phối kiến trúc Đa tác tử (Multi-Agent System) cho ASAS."""

    def __init__(
        self,
        llm_client: LLMClient,
        tool_registry: Optional[ToolRegistry] = None,
        memory_service: Optional[MemoryService] = None,
    ) -> None:
        self.llm_client = llm_client
        self.tool_registry = tool_registry
        self.memory_service = memory_service

        # Lắp ráp 4 tác tử chuyên biệt
        self.supervisor = SupervisorAgent(llm_client=self.llm_client)
        self.tutor = TutorAgent(llm_client=self.llm_client, tool_registry=self.tool_registry)
        self.evaluator = EvaluatorAgent(llm_client=self.llm_client)
        self.planner = PlannerAgent(llm_client=self.llm_client, memory_service=self.memory_service)

    async def dispatch(
        self,
        messages: List[Dict[str, Any]],
        student_id: Optional[str] = None,
    ) -> Tuple[SupervisorDecision, AgentResponse]:
        """Điều phối tin nhắn từ học sinh qua Supervisor tới Agent chuyên trách.

        Args:
            messages: Lịch sử tin nhắn trong phiên của học sinh.
            student_id: Mã định danh học sinh (cần thiết cho Planner).

        Returns:
            Tuple[SupervisorDecision, AgentResponse]: Quyết định phân luồng và kết quả phản hồi.
        """
        # 1. Supervisor phân tích ý định và ra quyết định
        decision = await self.supervisor.route(messages=messages)
        logger.info(
            f"[Multi-Agent Router] Next Agent: {decision.next_agent.value} | Lý do: {decision.reasoning}"
        )

        # 2. Chuyển giao nhiệm vụ (Handoff) cho Agent tương ứng
        if decision.next_agent == AgentRole.TUTOR:
            response = await self.tutor.run(
                messages=messages,
                instructions=decision.instructions,
            )
        elif decision.next_agent == AgentRole.EVALUATOR:
            response = await self.evaluator.run(
                messages=messages,
                instructions=decision.instructions,
            )
        elif decision.next_agent == AgentRole.PLANNER:
            response = await self.planner.run(
                messages=messages,
                student_id=student_id,
                instructions=decision.instructions,
            )
        else:
            # Fallback an toàn về Tutor
            response = await self.tutor.run(
                messages=messages,
                instructions=decision.instructions,
            )

        return decision, response


def create_default_orchestrator(
    llm_client: Optional[LLMClient] = None,
    tool_registry: Optional[ToolRegistry] = None,
    memory_service: Optional[MemoryService] = None,
) -> MultiAgentOrchestrator:
    """Hàm Factory khởi tạo MultiAgentOrchestrator với cấu hình mặc định."""
    client = llm_client or LLMClient()
    registry = tool_registry or create_default_registry()
    return MultiAgentOrchestrator(
        llm_client=client,
        tool_registry=registry,
        memory_service=memory_service,
    )
