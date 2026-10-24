"""Tutor Agent implementation with Socratic teaching methodology and tool calling integration."""

from typing import Any, Dict, List, Optional
from asas.core.llm_client import LLMClient
from asas.modules.agents.schemas import AgentResponse, AgentRole
from asas.modules.tools.registry import ToolRegistry

TUTOR_SYSTEM_PROMPT = """Bạn là Tutor Agent (Gia sư sư phạm Socratic) của hệ thống AI Study Assistant (ASAS).
Nguyên tắc sư phạm cốt lõi:
1. Phương pháp Gợi mở (Socratic Method): Không giải bài tập thay học sinh hay đưa ra đáp án cuối cùng ngay lập tức. Hãy chia nhỏ bài toán, đặt câu hỏi định hướng để học sinh tự tư duy và tìm ra lời giải.
2. Kiên nhẫn, thấu hiểu và khích lệ: Khi học sinh trả lời đúng một phần, hãy khen ngợi và dẫn dắt sang bước tiếp theo.
3. Tận dụng công cụ (Tools) với RÀO CHẮN BẢO MẬT:
   - Sử dụng công cụ tính toán ('calculator') hoặc chạy code an toàn ('python_executor') để kiểm tra tính đúng đắn của lời giải hoặc minh họa thuật toán.
   - QUY TẮC BẢO MẬT WEB SEARCH: Công cụ tìm kiếm web ('web_search') CHỈ ĐƯỢC PHÉP dùng để kiểm chứng tính xác thực của đề bài, tra cứu tài liệu học thuật nhằm giải đáp thắc mắc về câu hỏi hoặc phản hồi bài học. Tuyệt đối KHÔNG tìm kiếm web hộ người dùng các nội dung tra cứu tự do ngoài mục đích học tập (không đóng vai trò công cụ tìm kiếm thay người dùng)."""


class TutorAgent:
    """Tác tử Gia sư chuyên trách hướng dẫn, giải thích bài học theo phương pháp Socratic."""

    def __init__(
        self,
        llm_client: LLMClient,
        tool_registry: Optional[ToolRegistry] = None,
        system_prompt: Optional[str] = None,
    ) -> None:
        self.role = AgentRole.TUTOR
        self.llm_client = llm_client
        self.tool_registry = tool_registry
        self.system_prompt = system_prompt or TUTOR_SYSTEM_PROMPT

    async def run(
        self,
        messages: List[Dict[str, Any]],
        instructions: Optional[str] = None,
    ) -> AgentResponse:
        """Thực thi tác tử Tutor với ngữ cảnh hội thoại và chỉ đạo từ Supervisor.

        Args:
            messages: Danh sách tin nhắn trong phiên hội thoại.
            instructions: Chỉ dẫn bổ sung từ Supervisor Agent (nếu có).

        Returns:
            AgentResponse: Phản hồi sư phạm từ Tutor Agent.
        """
        effective_system_prompt = self.system_prompt
        if instructions:
            effective_system_prompt += f"\n\n[Chỉ đạo bổ sung từ Supervisor]: {instructions}"

        formatted_messages: List[Dict[str, Any]] = [
            {"role": "system", "content": effective_system_prompt}
        ]

        # Bổ sung các tin nhắn hội thoại (bỏ qua system message cũ để dùng system prompt của Tutor)
        for msg in messages:
            if msg.get("role") != "system":
                formatted_messages.append(msg)

        # Gọi LLM (có hỗ trợ gọi Tool nếu có ToolRegistry)
        if self.tool_registry:
            reply = await self.llm_client.chat_with_tools(
                messages=formatted_messages,
                tool_registry=self.tool_registry,
            )
        else:
            reply = await self.llm_client.chat_completion(
                messages=formatted_messages,
            )

        return AgentResponse(
            agent_role=self.role,
            content=reply,
            metadata={
                "has_tools": self.tool_registry is not None,
                "instructions_applied": instructions is not None,
            },
        )
