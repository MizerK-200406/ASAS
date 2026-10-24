"""Supervisor Agent implementation for intelligent intent routing and agent delegation."""

from typing import Any, Dict, List, Optional
from loguru import logger

from asas.core.llm_client import LLMClient
from asas.modules.agents.schemas import AgentRole, SupervisorDecision

SUPERVISOR_SYSTEM_PROMPT = """Bạn là Supervisor Agent (Tổng điều phối viên học tập) của hệ thống AI Study Assistant (ASAS).
Nhiệm vụ của bạn là đọc tin nhắn mới nhất và bối cảnh hội thoại của học sinh, sau đó phân tích và ra quyết định chuyển giao nhiệm vụ (routing) cho một trong ba Agent chuyên trách sau:

1. 'tutor':
   - Khi học sinh muốn giải thích lý thuyết, khái niệm, thuật toán.
   - Khi học sinh hỏi cách giải bài tập, gợi ý từng bước, hoặc hỏi đáp thông thường về kiến thức.
   - Ví dụ: "Giải thích giúp em thuật toán Dijkstra", "Tại sao 0.1 + 0.2 != 0.3 trong Python?".

2. 'evaluator':
   - Khi học sinh nộp bài giải, nộp đoạn code Python, hoặc nộp bài luận nhờ nhận xét, phản biện, chấm điểm hoặc tìm lỗi sai.
   - Ví dụ: "Nhờ thầy chấm giúp bài code này", "Lời giải phương trình này của em có đúng không?", "Tìm lỗi sai trong đoạn code sau".

3. 'planner':
   - Khi học sinh hỏi về lộ trình học tập, kế hoạch ôn thi, thời gian biểu, phân bổ thời gian hoặc hỏi "Em nên học gì tiếp theo?".
   - Ví dụ: "Lập giúp em kế hoạch ôn thi môn Toán 1 tuần", "Em nên làm gì để cải thiện điểm số gần đây?".

Yêu cầu xuất ra cấu trúc JSON chuẩn:
- next_agent: tutor | evaluator | planner
- reasoning: Lý giải ngắn gọn tại sao chọn agent này
- instructions: Chỉ dẫn nghiệp vụ cụ thể cho agent tiếp nhận (hoặc null nếu không có).

LƯU Ý QUAN TRỌNG: Hệ thống ASAS KHÔNG hỗ trợ tìm kiếm web hộ người dùng cho các nhu cầu tra cứu tự do ngoài mục đích học tập. Nếu học sinh yêu cầu tra cứu ngoài lề, hãy điều hướng tới 'tutor' để nhắc nhở học sinh tập trung vào bài học."""


class SupervisorAgent:
    """Tác tử Tổng điều phối phân tích ý định học sinh và điều hướng tới Agent chuyên trách."""

    def __init__(
        self,
        llm_client: LLMClient,
        system_prompt: Optional[str] = None,
    ) -> None:
        self.role = AgentRole.SUPERVISOR
        self.llm_client = llm_client
        self.system_prompt = system_prompt or SUPERVISOR_SYSTEM_PROMPT

    async def route(self, messages: List[Dict[str, Any]]) -> SupervisorDecision:
        """Phân tích ý định của học sinh và trả về quyết định điều phối có cấu trúc.

        Args:
            messages: Lịch sử tin nhắn của học sinh trong phiên.

        Returns:
            SupervisorDecision: Quyết định phân luồng gồm next_agent, reasoning, instructions.
        """
        try:
            user_messages = [msg for msg in messages if msg.get("role") != "system"]

            decision: SupervisorDecision = await self.llm_client.structured_output(
                messages=user_messages,
                response_model=SupervisorDecision,
                system_prompt=self.system_prompt,
                temperature=0.1,  # Nhiệt độ thấp để phân loại ý định chuẩn xác
            )
            return decision

        except Exception as e:
            logger.warning(f"Lỗi khi Supervisor phân loại ý định: {e}. Fallback an toàn về TutorAgent.")
            return SupervisorDecision(
                next_agent=AgentRole.TUTOR,
                reasoning=f"Fallback tự động về Tutor do lỗi phân tích ý định: {str(e)}",
                instructions="Hãy trả lời câu hỏi của học sinh một cách ân cần, sư phạm.",
            )
