"""Tác tử Thiết kế Đề thi & Khảo thí Sư phạm (QuizGeneratorAgent).

Chuyên trách:
- Thiết kế câu hỏi trắc nghiệm đạt chuẩn đo lường khảo thí.
- Xây dựng các phương án nhiễu (distractors) hợp lý.
- Bắt buộc gắn ngộ nhận lý thuyết (misconception) cho các phương án sai.
- Chuẩn hóa làm sạch và xáo trộn đáp án nhằm triệt tiêu thiên kiến vị trí (bias).
"""

import random
import re
from typing import Any, Dict, List, Optional
from loguru import logger

from asas.core.llm_client import LLMClient
from asas.core.tools import Tool
from asas.modules.agents.base import BaseAgent
from asas.modules.agents.schemas import AgentRole
from asas.modules.quiz.schemas import DifficultyLevel, Quiz, QuizGenerationRequest

GENERATOR_SYSTEM_PROMPT = (
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
    cleaned = re.sub(r"^\s*\[?[A-Fa-f0-9]\]?[\.\:\)\-\–\s]+\s*", "", cleaned)

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

        for opt in q.options:
            opt.text = sanitize_option_text(opt.text, opt.id)

        correct_text = None
        for opt in q.options:
            if opt.id == q.correct_answer_id:
                correct_text = opt.text
                break

        if correct_text is None:
            continue

        shuffled = list(q.options)
        random.shuffle(shuffled)

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


class QuizGeneratorAgent(BaseAgent):
    """Tác tử chuyên biệt tạo đề thi trắc nghiệm AI đạt chuẩn sư phạm."""

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        model: Optional[str] = None,
        tools: Optional[List[Tool]] = None,
    ) -> None:
        super().__init__(
            role=AgentRole.GENERATOR,
            system_prompt=GENERATOR_SYSTEM_PROMPT,
            llm_client=llm_client,
            model=model,
            tools=tools,
        )

    async def generate(self, request: QuizGenerationRequest) -> Quiz:
        """Thiết kế đề thi trắc nghiệm theo yêu cầu của học sinh."""
        cleaned_topic = sanitize_topic(request.topic)
        logger.info(
            f"[{self.role.value}] Bắt đầu thiết kế quiz cho chủ đề: '{cleaned_topic}' "
            f"(Gốc: '{request.topic}') | Số câu: {request.num_questions} | Độ khó: {request.difficulty.value}"
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
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        target_model = self.get_target_model()
        quiz = await self.llm_client.structured_output(
            messages=messages,
            response_model=Quiz,
            model=target_model,
            temperature=0.3,
            max_tokens=6144,
            student_id=request.student_id,
            action_type="generate_quiz",
        )

        quiz.topic = cleaned_topic
        quiz.source = "ai_generated"
        quiz = shuffle_quiz_options(quiz)

        logger.info(f"[{self.role.value}] Đã tạo thành công quiz '{quiz.title}' gồm {len(quiz.questions)} câu.")
        return quiz

    async def run(
        self,
        messages: List[Dict[str, Any]],
        instructions: Optional[str] = None,
    ) -> Quiz:
        """Thực thi sinh quiz từ ngữ cảnh hội thoại."""
        topic = messages[-1]["content"] if messages else "General Knowledge"
        req = QuizGenerationRequest(
            topic=topic,
            num_questions=3,
            difficulty=DifficultyLevel.MEDIUM,
            student_id=None,
        )
        return await self.generate(req)
