"""Dịch vụ điều phối (Orchestrator) tạo và chấm điểm đề thi trắc nghiệm AI."""

from typing import Dict, List, Optional
from loguru import logger

from asas.core.llm_client import LLMClient
from asas.modules.agents.evaluator import EvaluatorAgent
from asas.modules.agents.generator import (
    DIFFICULTY_PATTERNS,
    QuizGeneratorAgent,
    sanitize_option_text,
    sanitize_topic,
    shuffle_quiz_options,
)
from asas.modules.agents.schemas import EvaluationResult
from asas.modules.memory.service import MemoryService
from asas.modules.quiz.schemas import (
    Quiz,
    QuizGenerationRequest,
    QuizGradeResult,
)

__all__ = [
    "QuizService",
    "sanitize_topic",
    "sanitize_option_text",
    "shuffle_quiz_options",
    "DIFFICULTY_PATTERNS",
]


class QuizService:
    """Dịch vụ điều phối (Orchestrator) tạo đề, chấm điểm và kích hoạt các AI Agents."""

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        generator_agent: Optional[QuizGeneratorAgent] = None,
        evaluator_agent: Optional[EvaluatorAgent] = None,
        memory_service: Optional[MemoryService] = None,
    ):
        self.llm_client = llm_client or LLMClient()
        self.generator_agent = generator_agent or QuizGeneratorAgent(llm_client=self.llm_client)
        self.evaluator_agent = evaluator_agent or EvaluatorAgent(llm_client=self.llm_client)
        self.memory_service = memory_service

    async def generate_quiz(self, request: QuizGenerationRequest) -> Quiz:
        """Ủy quyền việc thiết kế đề thi cho QuizGeneratorAgent."""
        return await self.generator_agent.generate(request)

    def grade_quiz(self, quiz: Quiz, user_answers: Dict[int, str]) -> QuizGradeResult:
        """Chấm điểm bài làm của học sinh theo phương pháp tất định và trích xuất ngộ nhận có sẵn."""
        total_questions = len(quiz.questions)
        correct_count = 0
        details = []
        misconceptions: List[str] = []

        for index, question in enumerate(quiz.questions):
            user_choice = user_answers.get(index)
            is_correct = (user_choice == question.correct_answer_id) if user_choice is not None else False

            if is_correct:
                correct_count += 1

            # Trích xuất ngộ nhận từ phương án đã chọn nếu có
            detected_misconception = None
            if not is_correct and user_choice is not None:
                for opt in question.options:
                    if opt.id == user_choice and opt.misconception:
                        detected_misconception = opt.misconception
                        if opt.misconception not in misconceptions:
                            misconceptions.append(opt.misconception)
                        break

            details.append({
                "question_index": index,
                "question": question.question,
                "user_answer": user_choice,
                "correct_answer": question.correct_answer_id,
                "is_correct": is_correct,
                "explanation": question.explanation,
                "misconception": detected_misconception,
            })

        score_percentage = round((correct_count / total_questions) * 100.0, 2) if total_questions > 0 else 0.0

        logger.info(
            f"Hoàn thành chấm quiz: {correct_count}/{total_questions} câu đúng ({score_percentage}%)."
        )

        return QuizGradeResult(
            total_questions=total_questions,
            correct_count=correct_count,
            score_percentage=score_percentage,
            details=details,
            misconceptions=misconceptions,
        )

    async def evaluate_quiz_with_agent(
        self,
        quiz: Quiz,
        user_answers: Dict[int, str],
        grade_result: QuizGradeResult,
        student_name: Optional[str] = None,
    ) -> EvaluationResult:
        """Ủy quyền việc phân tích lỗ hổng kiến thức và lời khuyên sư phạm cho EvaluatorAgent."""
        return await self.evaluator_agent.evaluate_quiz(
            quiz=quiz,
            user_answers=user_answers,
            grade_result=grade_result,
            student_name=student_name,
        )
