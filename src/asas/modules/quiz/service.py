import random
import re
from typing import Dict, List, Optional
from loguru import logger

from asas.core.llm_client import LLMClient
from asas.modules.agents.evaluator import EvaluatorAgent
from asas.modules.agents.schemas import EvaluationResult
from asas.modules.memory.service import MemoryService
from asas.modules.quiz.schemas import (
    Quiz,
    QuizGenerationRequest,
    QuizGradeResult,
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


def sanitize_option_text(text: str, option_id: Optional[str] = None) -> str:
    """Làm sạch nội dung phương án, loại bỏ tiền tố A., B), C: hoặc ký tự chữ cái dính liền do LLM sinh ra."""
    cleaned = text.strip()
    # 1. Bỏ tiền tố dạng 'A. ', 'A) ', 'A: ', 'A - ', '[A] '
    cleaned = re.sub(r"^\s*\[?[A-Fa-f0-9]\]?[\.\:\)\-\–\s]+\s*", "", cleaned)

    # 2. Xử lý trường hợp chữ cái đáp án dính liền vào từ viết hoa tiếp theo (ví dụ: 'ANormalization')
    if option_id and len(cleaned) > 1 and cleaned.startswith(option_id):
        second_char = cleaned[1]
        if second_char.isupper():
            cleaned = cleaned[1:].strip()

    return cleaned if cleaned else text.strip()


def shuffle_quiz_options(quiz: Quiz) -> Quiz:
    """Làm sạch tiền tố phương án và xáo trộn ngẫu nhiên thứ tự các options của từng câu hỏi và gán lại ID (A, B, C, D)

    để loại bỏ bias vị trí đáp án đúng do LLM sinh ra.
    """
    for q in quiz.questions:
        if not q.options or len(q.options) < 2:
            continue

        # 1. Chuẩn hóa làm sạch text của từng option trước khi xáo trộn
        for opt in q.options:
            opt.text = sanitize_option_text(opt.text, opt.id)

        # 2. Tìm nội dung của đáp án đúng hiện tại
        correct_text = None
        for opt in q.options:
            if opt.id == q.correct_answer_id:
                correct_text = opt.text
                break

        if correct_text is None:
            continue

        # Xáo trộn danh sách options
        shuffled = list(q.options)
        random.shuffle(shuffled)

        # Gán lại ID theo thứ tự A, B, C, D... và cập nhật correct_answer_id
        letters = ["A", "B", "C", "D", "E", "F"]
        new_correct_id = None

        for idx, opt in enumerate(shuffled):
            new_id = letters[idx] if idx < len(letters) else str(idx + 1)
            if opt.text == correct_text:
                new_correct_id = new_id
            opt.id = new_id

        if new_correct_id is not None:
            q.options = shuffled
            q.correct_answer_id = new_correct_id

    return quiz


class QuizService:
    """Dịch vụ tạo và chấm điểm đề thi trắc nghiệm AI trực tiếp."""

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        evaluator_agent: Optional[EvaluatorAgent] = None,
        memory_service: Optional[MemoryService] = None,
    ):
        self.llm_client = llm_client or LLMClient()
        self.evaluator_agent = evaluator_agent or EvaluatorAgent(llm_client=self.llm_client)
        self.memory_service = memory_service

    async def generate_quiz(self, request: QuizGenerationRequest) -> Quiz:
        """Tạo bộ câu hỏi trắc nghiệm trực tiếp từ AI model (không lưu vào ngân hàng câu hỏi)."""
        cleaned_topic = sanitize_topic(request.topic)
        logger.info(
            f"Bắt đầu tạo quiz trực tiếp từ AI cho chủ đề: '{cleaned_topic}' (Gốc: '{request.topic}') | "
            f"Số câu: {request.num_questions} | Độ khó: {request.difficulty.value}"
        )

        # Gọi AI sinh câu hỏi mới (kèm trường ngộ nhận misconception cho đáp án sai)
        system_prompt = (
            "Bạn là một chuyên gia giáo dục và khảo thí AI cao cấp. "
            "Nhiệm vụ của bạn là thiết kế một bộ câu hỏi kiểm tra kiến thức (Quiz) đạt chuẩn sư phạm:\n"
            "1. Câu hỏi rõ ràng, tập trung vào bản chất khái niệm hoặc ứng dụng thực tế.\n"
            "2. Các phương án sai (distractors) phải hợp lý, và BẮT BUỘC có trường 'misconception' "
            "giải thích ngắn gọn ngộ nhận lý thuyết hoặc lỗ hổng kiến thức khi học sinh chọn nhầm phương án đó (đối với phương án đúng, misconception để null).\n"
            "3. Duy nhất một đáp án đúng chính xác tuyệt đối.\n"
            "4. Phần giải thích (explanation) phải ngắn gọn, súc tích chỉ rõ tại sao đáp án đó là đúng về mặt kiến thức.\n"
            "5. Không cần bận tâm về việc cân đối vị trí đáp án đúng (hệ thống sẽ tự động xáo trộn ngẫu nhiên sau khi tạo).\n"
            "6. Tuyệt đối không sinh các cặp ngoặc rỗng ({}, }}). Giữ nội dung cô đọng để hoàn tất đầy đủ cấu trúc JSON.\n"
            "7. Trường 'text' của mỗi lựa chọn chỉ chứa nội dung phương án, tuyệt đối không bắt đầu bằng tiền tố 'A. ', 'B. ' hay ký tự chữ cái đáp án."
        )

        user_prompt = (
            f"Hãy tạo một bộ câu hỏi kiểm tra về chủ đề: '{cleaned_topic}'.\n"
            f"- Số lượng câu hỏi: {request.num_questions}\n"
            f"- Mức độ khó bắt buộc: {request.difficulty.value}.\n"
            f"- Ngôn ngữ yêu cầu: {request.language}\n"
            f"- Đảm bảo mỗi câu hỏi có 4 lựa chọn (A, B, C, D) với correct_answer_id hợp lệ.\n"
            "- Trường 'text' chỉ chứa nội dung đáp án (không chèn tiền tố 'A.', 'B.').\n"
            f"- Với mỗi phương án sai, bắt buộc điền lý do ngộ nhận vào trường 'misconception'.\n"
            "- Hãy hoàn tất đầy đủ mọi câu hỏi và đóng mảng JSON đúng cú pháp."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        model = getattr(getattr(self.llm_client, "settings", None), "generator_model", None)
        quiz = await self.llm_client.structured_output(
            messages=messages,
            response_model=Quiz,
            model=model,
            temperature=0.3,
            max_tokens=6144,
            student_id=request.student_id,
            action_type="generate_quiz",
        )

        # Cập nhật topic và nguồn gốc
        quiz.topic = cleaned_topic
        quiz.source = "ai_generated"

        # Xáo trộn các đáp án ngẫu nhiên để triệt tiêu bias
        quiz = shuffle_quiz_options(quiz)

        logger.info(f"Đã tạo thành công quiz '{quiz.title}' gồm {len(quiz.questions)} câu hỏi (AI sinh mới).")
        return quiz

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
        """Kích hoạt EvaluatorAgent để phân tích lỗ hổng kiến thức và đưa ra lời khuyên."""
        return await self.evaluator_agent.evaluate_quiz(
            quiz=quiz,
            user_answers=user_answers,
            grade_result=grade_result,
            student_name=student_name,
        )
