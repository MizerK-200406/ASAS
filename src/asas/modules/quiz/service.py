import random
import re
from typing import Dict, List, Optional
from loguru import logger

from asas.core.llm_client import LLMClient
from asas.modules.agents.evaluator import EvaluatorAgent
from asas.modules.agents.schemas import EvaluationResult
from asas.modules.quiz.schemas import (
    Quiz,
    QuizGenerationRequest,
    QuizGradeResult,
    QuizOption,
    QuizQuestion,
)

DIFFICULTY_PATTERNS = [
    r"(?i)\s*[\(\[\{]\s*(?:mức\s*độ|độ\s*khó|cấp\s*độ|level)?\s*[:=\-]?\s*(?:dễ|cơ\s*bản|trung\s*bình|vừa|khó|nâng\s*cao|chuyên\s*sâu|easy|medium|hard|basic|intermediate|advanced)\s*[\)\]\}]",
    r"(?i)\s*[-–—:]\s*(?:mức\s*độ|độ\s*khó|cấp\s*độ|level)?\s*[:=\-]?\s*(?:dễ|cơ\s*bản|trung\s*bình|vừa|khó|nâng\s*cao|chuyên\s*sâu|easy|medium|hard|basic|intermediate|advanced)\s*$",
    r"(?i)\s*(?:mức\s*độ|độ\s*khó|cấp\s*độ|level)\s*[:=\-]?\s*(?:dễ|cơ\s*bản|trung\s*bình|vừa|khó|nâng\s*cao|chuyên\s*sâu|easy|medium|hard|basic|intermediate|advanced)\b",
    r"(?i)\s+\b(?:dễ|cơ\s*bản|nâng\s*cao|khó|easy|hard|medium)\b\s*$",
]


def sanitize_topic(topic: str) -> str:
    """Loại bỏ các từ khóa chỉ mức độ/độ khó khỏi chuỗi chủ đề nếu người dùng vô tình nhập kèm."""
    cleaned = topic.strip()
    for pattern in DIFFICULTY_PATTERNS:
        cleaned = re.sub(pattern, "", cleaned).strip()
    return cleaned if cleaned else topic.strip()


def shuffle_quiz_options(quiz: Quiz) -> Quiz:
    """Xáo trộn ngẫu nhiên các lựa chọn đáp án và cập nhật lại correct_answer_id để phân bổ đều vị trí A, B, C, D."""
    for q in quiz.questions:
        if not q.options or len(q.options) <= 1:
            continue

        target_opt_id = q.correct_answer_id
        options = list(q.options)
        random.shuffle(options)

        standard_labels = [chr(ord("A") + i) for i in range(len(options))]
        new_correct_id = target_opt_id
        new_options: List[QuizOption] = []

        for idx, opt in enumerate(options):
            new_id = standard_labels[idx]
            if opt.id == target_opt_id:
                new_correct_id = new_id
            new_options.append(QuizOption(id=new_id, text=opt.text))

        q.options = new_options
        q.correct_answer_id = new_correct_id

    return quiz


class QuizService:
    """Service xử lý tạo đề trắc nghiệm, chấm điểm bài làm và điều phối Evaluator Agent."""

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        evaluator_agent: Optional[EvaluatorAgent] = None,
    ):
        self.llm_client = llm_client or LLMClient()
        self.evaluator_agent = evaluator_agent or EvaluatorAgent(llm_client=self.llm_client)

    async def generate_quiz(self, request: QuizGenerationRequest) -> Quiz:
        """Tạo bộ câu hỏi trắc nghiệm chất lượng cao dựa trên yêu cầu của học sinh."""
        cleaned_topic = sanitize_topic(request.topic)
        logger.info(
            f"Bắt đầu tạo quiz cho chủ đề: '{cleaned_topic}' (Gốc: '{request.topic}') | "
            f"Số câu: {request.num_questions} | Độ khó chỉ định: {request.difficulty.value}"
        )

        system_prompt = (
            "Bạn là một chuyên gia giáo dục và khảo thí AI cao cấp. "
            "Nhiệm vụ của bạn là thiết kế một bộ câu hỏi kiểm tra kiến thức (Quiz) đạt chuẩn sư phạm:\n"
            "1. Câu hỏi rõ ràng, tập trung vào bản chất khái niệm hoặc ứng dụng thực tế.\n"
            "2. Các phương án sai (distractors) phải hợp lý, phản ánh đúng những lỗi sai phổ biến của người học.\n"
            "3. Duy nhất một đáp án đúng chính xác tuyệt đối.\n"
            "4. Phần giải thích (explanation) phải ngắn gọn, súc tích và chỉ rõ tại sao đáp án đó là đúng về mặt kiến thức, tránh viết phụ thuộc cứng vào nhãn 'Đáp án A'.\n"
            "5. Không cần bận tâm về việc cân đối vị trí đáp án đúng (hệ thống sẽ tự động xáo trộn ngẫu nhiên sau khi tạo). Hãy tập trung xuất trực tiếp JSON nhanh chóng, chính xác và cô đọng.\n"
            "6. Tuyệt đối không sinh các cặp ngoặc rỗng ({}, }}). Giữ nội dung cô đọng để hoàn tất đầy đủ cấu trúc JSON."
        )

        user_prompt = (
            f"Hãy tạo một bộ câu hỏi kiểm tra về chủ đề: '{cleaned_topic}'.\n"
            f"- Số lượng câu hỏi: {request.num_questions}\n"
            f"- Mức độ khó bắt buộc: {request.difficulty.value} (Nếu chủ đề có từ khóa gợi ý độ khó khác, hãy bỏ qua và tuân thủ tuyệt đối mức độ này).\n"
            f"- Ngôn ngữ yêu cầu: {request.language}\n"
            f"- Đảm bảo mỗi câu hỏi có 4 lựa chọn (A, B, C, D) với correct_answer_id hợp lệ.\n"
            "- Không cần bận tâm về việc xáo trộn đáp án đúng (hệ thống backend sẽ tự động xáo trộn sau khi nhận kết quả).\n"
            "- Hãy hoàn tất đầy đủ mọi câu hỏi và đóng mảng JSON đúng cú pháp."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        quiz = await self.llm_client.structured_output(
            messages=messages,
            response_model=Quiz,
            temperature=0.3,
            max_tokens=6144,
        )

        # Cập nhật topic đã được làm sạch
        quiz.topic = cleaned_topic

        # Xáo trộn các đáp án ngẫu nhiên để triệt tiêu bias đáp án A
        quiz = shuffle_quiz_options(quiz)

        logger.info(f"Đã tạo thành công quiz '{quiz.title}' gồm {len(quiz.questions)} câu hỏi (đã xáo trộn đáp án).")
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

    async def evaluate_quiz_with_agent(
        self,
        quiz: Quiz,
        user_answers: Dict[int, str],
        grade_result: QuizGradeResult,
        student_name: Optional[str] = None,
    ) -> EvaluationResult:
        """Kích hoạt EvaluatorAgent để phân tích lỗ hổng kiến thức và đưa ra lời khuyên."""
        return await self.evaluator_agent.evaluate_quiz(
            quiz=quiz,
            user_answers=user_answers,
            grade_result=grade_result,
            student_name=student_name,
        )
