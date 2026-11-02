"""Evaluator Agent implementation for general evaluation and quiz knowledge gap analysis."""

from typing import Any, Dict, List, Optional
from loguru import logger

from asas.core.llm_client import LLMClient
from asas.modules.agents.schemas import AgentResponse, AgentRole, EvaluationResult
from asas.modules.quiz.schemas import Quiz, QuizGradeResult

EVALUATOR_SYSTEM_PROMPT = """Bạn là Evaluator Agent - Chuyên gia Đánh giá Sư phạm và Phân tích Lỗ hổng Kiến thức của hệ thống ASAS.
Nhiệm vụ cốt lõi của bạn:
1. Đánh giá bài làm của học sinh một cách khách quan, mang tính xây dựng và sư phạm sâu sắc.
2. Xác định chính xác các LỖ HỔNG KIẾN THỨC (Knowledge Gaps), ngộ nhận khái niệm, hoặc sai sót trong tư duy logic.
3. Chỉ ra rõ ràng các ĐIỂM MẠNH (Strengths) đối với các phần học sinh đã làm tốt để khích lệ tinh thần.
4. Đưa ra LỜI KHUYÊN (Recommendations) thiết thực và KẾ HOẠCH HÀNH ĐỘNG (Improvement Plan) từng bước giúp học sinh bồi đắp kiến thức còn thiếu."""


class EvaluatorAgent:
    """Tác tử Đánh giá dùng chung cho toàn bộ hệ thống ASAS."""

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        system_prompt: Optional[str] = None,
    ) -> None:
        self.role = AgentRole.EVALUATOR
        self.llm_client = llm_client or LLMClient()
        self.system_prompt = system_prompt or EVALUATOR_SYSTEM_PROMPT

    async def evaluate_general(
        self,
        context: str,
        criteria: Optional[str] = None,
    ) -> EvaluationResult:
        """Đánh giá tổng quát nội dung học tập, bài tập hoặc lời giải (mở rộng sau này)."""
        prompt = f"Hãy đánh giá nội dung học tập sau:\n\n{context}"
        if criteria:
            prompt += f"\n\nTiêu chí đánh giá bổ sung:\n{criteria}"

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt},
        ]
        return await self.llm_client.structured_output(
            messages=messages,
            response_model=EvaluationResult,
            temperature=0.2,
        )

    async def evaluate_quiz(
        self,
        quiz: Quiz,
        user_answers: Dict[int, str],
        grade_result: QuizGradeResult,
        student_name: Optional[str] = None,
    ) -> EvaluationResult:
        """Chuyên biệt: Phân tích bài thi trắc nghiệm để phát hiện lỗ hổng kiến thức và đưa ra lời khuyên."""
        name = student_name or "Học sinh"

        # Tổng hợp các câu làm sai và câu làm đúng
        correct_items = []
        wrong_items = []

        for detail in grade_result.details:
            q_idx = detail["question_index"]
            q_obj = quiz.questions[q_idx] if q_idx < len(quiz.questions) else None
            q_text = q_obj.question if q_obj else f"Câu {q_idx + 1}"
            explanation = detail.get("explanation", "")

            if detail["is_correct"]:
                correct_items.append(f"- Câu {q_idx + 1}: {q_text} (Chọn đúng: {detail['user_answer']})")
            else:
                user_ans = detail["user_answer"]
                correct_ans = detail["correct_answer"]
                wrong_items.append(
                    f"- Câu {q_idx + 1}: {q_text}\n"
                    f"  + Đáp án học sinh chọn: {user_ans}\n"
                    f"  + Đáp án đúng: {correct_ans}\n"
                    f"  + Giải thích kiến thức: {explanation}"
                )

        correct_str = "\n".join(correct_items) if correct_items else "Không có câu nào đúng."
        wrong_str = "\n".join(wrong_items) if wrong_items else "Không có câu làm sai (Làm đúng 100%)."

        prompt = (
            f"Học sinh '{name}' vừa hoàn thành bài trắc nghiệm về chủ đề '{quiz.topic}'.\n"
            f"Kết quả điểm số: {grade_result.correct_count}/{grade_result.total_questions} "
            f"({grade_result.score_percentage}%).\n\n"
            f"### DANH SÁCH CÂU LÀM ĐÚNG:\n{correct_str}\n\n"
            f"### DANH SÁCH CÂU LÀM SAI VÀ NGUYÊN NHÂN:\n{wrong_str}\n\n"
            f"YÊU CẦU ĐÁNH GIÁ:\n"
            f"1. Xác định cụ thể các lỗ hổng kiến thức (knowledge_gaps) mà học sinh đang mắc phải dựa trên các câu sai.\n"
            f"2. Ghi nhận các điểm mạnh (strengths) ở những câu làm đúng.\n"
            f"3. Viết nhận xét phê bình sư phạm (critique) phân tích tại sao học sinh chọn nhầm hoặc ngộ nhận.\n"
            f"4. Đưa ra các khuyến nghị, chủ đề trọng tâm cần ôn tập lại (recommendations).\n"
            f"5. Đề xuất kế hoạch hành động cụ thể từng bước (improvement_plan)."
        )

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt},
        ]

        logger.info(f"[EvaluatorAgent] Bắt đầu đánh giá lỗ hổng kiến thức Quiz cho {name}...")
        evaluation = await self.llm_client.structured_output(
            messages=messages,
            response_model=EvaluationResult,
            temperature=0.2,
        )
        return evaluation

    async def run(
        self,
        messages: List[Dict[str, Any]],
        instructions: Optional[str] = None,
    ) -> AgentResponse:
        """Thực thi đánh giá từ chuỗi tin nhắn và trả về AgentResponse."""
        prompt = messages[-1]["content"] if messages else ""
        if instructions:
            prompt += f"\n\n[Lưu ý thêm]: {instructions}"

        eval_result = await self.evaluate_general(context=prompt)
        rendered_content = (
            f"📊 Nhận xét: {eval_result.critique}\n"
            f"🔍 Lỗ hổng kiến thức: {', '.join(eval_result.knowledge_gaps)}\n"
            f"💡 Lời khuyên: {', '.join(eval_result.recommendations)}"
        )
        return AgentResponse(
            agent_role=self.role,
            evaluation=eval_result,
            content=rendered_content,
        )
