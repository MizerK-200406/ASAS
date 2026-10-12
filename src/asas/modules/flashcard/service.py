from typing import List, Optional
from loguru import logger

from asas.core.llm_client import LLMClient
from asas.modules.flashcard.schemas import (
    FlashcardGenerationRequest,
    FlashcardItem,
    FlashcardSet,
)


class FlashcardService:
    """Service xử lý tạo và quản lý thẻ ghi nhớ (Flashcards)."""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or LLMClient()

    async def generate_flashcards(
        self, request: FlashcardGenerationRequest
    ) -> FlashcardSet:
        """Tạo bộ thẻ ghi nhớ tối ưu cho phương pháp Active Recall & Spaced Repetition."""
        logger.info(
            f"Bắt đầu tạo flashcards cho: '{request.content_or_topic[:50]}...' | "
            f"Số lượng: {request.num_cards} thẻ"
        )

        system_prompt = (
            "Bạn là chuyên gia tâm lý học nhận thức và phương pháp ghi nhớ khoa học (Active Recall & Spaced Repetition). "
            "Nhiệm vụ của bạn là chuyển đổi tài liệu hoặc chủ đề học tập thành các thẻ ghi nhớ (Flashcards) chất lượng cao tuân theo 'Nguyên lý Thông tin Tối thiểu' (Minimum Information Principle):\n"
            "1. Mặt trước (front): Đặt một câu hỏi hoặc khái niệm đơn lẻ, rõ ràng, kích thích tư duy truy hồi chủ động.\n"
            "2. Mặt sau (back): Trả lời trọng tâm, súc tích, chỉ chứa ý chính quan trọng nhất, tránh viết lan man dài dòng.\n"
            "3. Gợi ý (hint): Cung cấp một manh mối tư duy ngắn gọn giúp người học tự nhớ ra khi bị kẹt mà không lộ thẳng đáp án.\n"
            "4. Thẻ phân loại (tags): Gán 2-3 nhãn chủ đề phù hợp bằng chữ thường (ví dụ: 'machine-learning', 'python')."
        )

        user_prompt = (
            f"Hãy trích xuất và tạo {request.num_cards} thẻ ghi nhớ từ nội dung/chủ đề sau:\n"
            f"'''\n{request.content_or_topic}\n'''\n"
            f"- Ngôn ngữ yêu cầu: {request.language}\n"
            f"- Mỗi thẻ phải súc tích, dễ nhớ và có đầy đủ front, back, hint, tags."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        flashcard_set = await self.llm_client.structured_output(
            messages=messages,
            response_model=FlashcardSet,
        )

        logger.info(
            f"Đã tạo thành công bộ flashcard '{flashcard_set.topic}' gồm {len(flashcard_set.cards)} thẻ."
        )
        return flashcard_set

    def filter_by_tag(self, flashcard_set: FlashcardSet, tag: str) -> List[FlashcardItem]:
        """Lọc các thẻ ghi nhớ theo nhãn phân loại (không phân biệt chữ hoa/thường)."""
        normalized_tag = tag.strip().lower()
        return [
            card
            for card in flashcard_set.cards
            if any(t.lower() == normalized_tag for t in card.tags)
        ]
