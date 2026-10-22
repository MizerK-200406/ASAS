"""Planner Agent implementation for generating personalized learning plans from memory data."""

from typing import Any, Dict, List, Optional
from asas.core.llm_client import LLMClient
from asas.modules.agents.schemas import AgentResponse, AgentRole
from asas.modules.memory.service import MemoryService

PLANNER_SYSTEM_PROMPT = """Bạn là Planner Agent (Chuyên gia tư vấn giáo dục & Thiết kế lộ trình học tập) của hệ thống AI Study Assistant (ASAS).
Nhiệm vụ cốt lõi của bạn:
1. Phân tích tình hình học tập thực tế của học sinh (dựa trên lịch sử điểm số bài kiểm tra và các thẻ Flashcard đến hạn ôn tập nếu có).
2. Nhận diện các chủ đề học sinh còn yếu (điểm số < 70%) để ưu tiên bổ trợ.
3. Thiết kế lộ trình học tập cá nhân hóa, khả thi, rõ ràng theo từng giai đoạn (ví dụ: từng ngày, từng buổi).
4. Phân bổ hợp lý giữa việc học kiến thức mới, làm bài tập thực hành và ôn tập ngắt quãng (Flashcards)."""


class PlannerAgent:
    """Tác tử Lập kế hoạch chuyên phân tích dữ liệu bộ nhớ học sinh và đề xuất lộ trình tối ưu."""

    def __init__(
        self,
        llm_client: LLMClient,
        memory_service: Optional[MemoryService] = None,
        system_prompt: Optional[str] = None,
    ) -> None:
        self.role = AgentRole.PLANNER
        self.llm_client = llm_client
        self.memory_service = memory_service
        self.system_prompt = system_prompt or PLANNER_SYSTEM_PROMPT

    async def run(
        self,
        messages: List[Dict[str, Any]],
        student_id: Optional[str] = None,
        instructions: Optional[str] = None,
    ) -> AgentResponse:
        """Thực thi tác tử Planner để sinh lộ trình học tập.

        Args:
            messages: Lịch sử tin nhắn bao gồm yêu cầu của học sinh.
            student_id: Mã học sinh (dùng để truy vấn lịch sử học tập từ MemoryService).
            instructions: Chỉ đạo bổ sung từ Supervisor (nếu có).

        Returns:
            AgentResponse: Kế hoạch hoặc lộ trình học tập chi tiết.
        """
        memory_context = ""
        has_memory_context = False

        if self.memory_service and student_id:
            try:
                summary = await self.memory_service.get_student_summary(student_id)
                due_cards = await self.memory_service.get_due_flashcards(student_id)
                profile = summary["profile"]
                stats = summary["quiz_stats"]
                recent = summary["recent_quizzes"]

                profile_details = [f"- Họ tên: {profile.name} (ID: {profile.student_id})"]
                if profile.grade_level:
                    profile_details.append(f"- Khối / Lớp: {profile.grade_level}")
                if profile.school:
                    profile_details.append(f"- Trường: {profile.school}")
                if profile.target_goal:
                    profile_details.append(f"- Mục tiêu học tập: {profile.target_goal}")
                if profile.learning_style:
                    profile_details.append(f"- Phong cách học: {profile.learning_style}")
                profile_text = "\n".join(profile_details)

                quiz_lines = []
                for q in recent:
                    line = f"- Chủ đề: {q.topic} | Điểm: {q.score_percentage}% ({q.correct_count}/{q.total_questions})"
                    if q.ai_critique:
                        line += f" | AI Nhận xét cần cải thiện: {q.ai_critique}"
                    if q.improvement_plan:
                        line += f" | Đề xuất: {q.improvement_plan}"
                    quiz_lines.append(line)
                recent_text = "\n".join(quiz_lines) if quiz_lines else "Chưa có bài quiz nào."

                memory_context = (
                    f"\n\n[HỒ SƠ HỌC SINH TỪ CƠ SỞ DỮ LIỆU]:\n"
                    f"{profile_text}\n"
                    f"- Thống kê Quiz: Tổng {stats['total_quizzes']} bài, Điểm trung bình: {stats['average_score']}%\n"
                    f"- Các bài Quiz gần nhất:\n{recent_text}\n"
                    f"- Số thẻ Flashcard đến hạn ôn hôm nay: {len(due_cards)} thẻ."
                )
                has_memory_context = True
            except Exception:
                pass

        effective_system_prompt = self.system_prompt + memory_context
        if instructions:
            effective_system_prompt += f"\n\n[Yêu cầu định hướng từ Supervisor]: {instructions}"

        formatted_messages: List[Dict[str, Any]] = [
            {"role": "system", "content": effective_system_prompt}
        ]

        for msg in messages:
            if msg.get("role") != "system":
                formatted_messages.append(msg)

        plan_text = await self.llm_client.chat_completion(
            messages=formatted_messages,
            temperature=0.3,
        )

        return AgentResponse(
            agent_role=self.role,
            content=plan_text,
            metadata={
                "has_memory_context": has_memory_context,
                "instructions_applied": instructions is not None,
            },
        )
