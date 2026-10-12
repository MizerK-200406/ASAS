from typing import Dict, Optional
from loguru import logger

from asas.core.llm_client import LLMClient
from asas.modules.quiz.schemas import (
    Quiz,
    QuizGenerationRequest,
    QuizGradeResult,
)


class QuizService:
    """Service xử lý tạo đề trắc nghiệm và chấm điểm bài làm."""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or LLMClient()

    async def generate_quiz(self, request: QuizGenerationRequest) -> Quiz:
        """Tạo bộ câu hỏi trắc nghiệm chất lượng cao dựa trên yêu cầu của học sinh."""
        logger.info(
            f"Bắt đầu tạo quiz cho chủ đề: '{request.topic}' | "
            f"Số câu: {request.num_questions} | Độ khó: {request.difficulty.value}"
        )

        system_prompt = (
            "Bạn là một chuyên gia giáo dục và khảo thí AI cao cấp. "
            "Nhiệm vụ của bạn là thiết kế một bộ câu hỏi kiểm tra kiến thức (Quiz) đạt chuẩn sư phạm:\n"
            "1. Câu hỏi rõ ràng, tập trung vào bản chất khái niệm hoặc ứng dụng thực tế.\n"
            "2. Các phương án sai (distractors) phải hợp lý, phản ánh đúng những lỗi sai phổ biến của người học.\n"
            "3. Duy nhất một đáp án đúng chính xác tuyệt đối.\n"
            "4. Phần giải thích (explanation) phải ngắn gọn, súc tích và chỉ rõ tại sao đáp án đó là đúng."
        )

        user_prompt = (
            f"Hãy tạo một bộ câu hỏi kiểm tra về chủ đề: '{request.topic}'.\n"
            f"- Số lượng câu hỏi: {request.num_questions}\n"
            f"- Mức độ khó: {request.difficulty.value}\n"
            f"- Ngôn ngữ yêu cầu: {request.language}\n"
            f"- Đảm bảo mỗi câu hỏi có 4 lựa chọn (A, B, C, D) với correct_answer_id hợp lệ."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        quiz = await self.llm_client.structured_output(
            messages=messages,
            response_model=Quiz,
        )

        logger.info(f"Đã tạo thành công quiz '{quiz.title}' gồm {len(quiz.questions)} câu hỏi.")
        return quiz

    def grade_quiz(self, quiz: Quiz, user_answers: Dict[int, str]) -> QuizGradeResult:
        """Chấm điểm bài làm của học sinh theo phương pháp tất định (Deterministic grading)."""
        total_questions = len(quiz.questions)
        correct_count = 0
        details = []

        for index, question in enumerate(quiz.questions):
            user_choice = user_answers.get(index)
            is_correct = (user_choice == question.correct_answer_id) if user_choice is not None else False

            if is_correct:
                correct_count += 1

            details.append({
                "question_index": index,
                "question": question.question,
                "user_answer": user_choice,
                "correct_answer": question.correct_answer_id,
                "is_correct": is_correct,
                "explanation": question.explanation,
            })

        score_percentage = round((correct_count / total_questions) * 100.0, 2) if total_questions > 0 else 0.0

        logger.info(f"Hoàn thành chấm quiz: {correct_count}/{total_questions} câu đúng ({score_percentage}%).")

        return QuizGradeResult(
            total_questions=total_questions,
            correct_count=correct_count,
            score_percentage=score_percentage,
            details=details,
        )
