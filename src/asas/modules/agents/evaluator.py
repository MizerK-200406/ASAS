"""Evaluator Agent implementation for rigorous grading, critique, and logic analysis."""

from typing import Any, Dict, List, Optional
from asas.core.llm_client import LLMClient
from asas.modules.agents.schemas import AgentResponse, AgentRole

EVALUATOR_SYSTEM_PROMPT = """Bạn là Evaluator Agent (Thầy giáo chấm bài & Chuyên gia phản biện logic) của hệ thống AI Study Assistant (ASAS).
Nhiệm vụ cốt lõi của bạn:
1. Đánh giá khách quan, nghiêm khắc nhưng mang tính xây dựng đối với bài làm, code hoặc lời giải của học sinh.
2. Cấu trúc phản hồi luôn gồm 3 phần rõ ràng:
   - 🌟 Điểm mạnh (Strengths): Những điểm học sinh làm đúng, tư duy mạch lạc hoặc cách tiếp cận tốt.
   - ⚠️ Lỗi sai & Lỗ hổng logic (Errors & Critique): Chỉ rõ từng dòng, từng bước suy luận có sai sót (ví dụ: edge-case, lỗi cú pháp, tính toán nhầm, ngộ nhận lý thuyết).
   - 💡 Hướng dẫn khắc phục (Actionable Improvements): Đưa ra gợi ý cách sửa hoặc code/lời giải chuẩn xác để học sinh tự hoàn thiện.
3. Không phán xét tiêu cực; luôn giữ thái độ tôn trọng, khích lệ tinh thần học tập."""


class EvaluatorAgent:
    """Tác tử Giám khảo/Phản biện chuyên chấm bài, phân tích lỗi sai và đưa ra nhận xét chi tiết."""

    def __init__(
        self,
        llm_client: LLMClient,
        system_prompt: Optional[str] = None,
    ) -> None:
        self.role = AgentRole.EVALUATOR
        self.llm_client = llm_client
        self.system_prompt = system_prompt or EVALUATOR_SYSTEM_PROMPT

    async def run(
        self,
        messages: List[Dict[str, Any]],
        instructions: Optional[str] = None,
    ) -> AgentResponse:
        """Thực thi đánh giá bài làm của học sinh.

        Args:
            messages: Lịch sử tin nhắn bao gồm bài làm cần chấm của học sinh.
            instructions: Chỉ đạo bổ sung về tiêu chí chấm từ Supervisor (nếu có).

        Returns:
            AgentResponse: Bản nhận xét và chấm điểm chi tiết.
        """
        effective_system_prompt = self.system_prompt
        if instructions:
            effective_system_prompt += f"\n\n[Tiêu chí đánh giá bổ sung từ Supervisor]: {instructions}"

        formatted_messages: List[Dict[str, Any]] = [
            {"role": "system", "content": effective_system_prompt}
        ]

        for msg in messages:
            if msg.get("role") != "system":
                formatted_messages.append(msg)

        evaluation_text = await self.llm_client.chat_completion(
            messages=formatted_messages,
            temperature=0.1,  # Nhiệt độ thấp để đánh giá logic chính xác, nhất quán
        )

        return AgentResponse(
            agent_role=self.role,
            content=evaluation_text,
            metadata={
                "instructions_applied": instructions is not None,
            },
        )
