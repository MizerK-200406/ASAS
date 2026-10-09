from typing import List, Optional
from pydantic import BaseModel, Field


class FlashcardItem(BaseModel):
    """Một thẻ ghi nhớ (Flashcard) hoàn chỉnh."""
    front: str = Field(..., description="Mặt trước: Khái niệm, từ vựng hoặc câu hỏi trọng tâm")
    back: str = Field(..., description="Mặt sau: Định nghĩa, giải thích hoặc câu trả lời cốt lõi")
    hint: Optional[str] = Field(default=None, description="Gợi ý hỗ trợ người học khi cần")
    tags: List[str] = Field(default_factory=list, description="Thẻ phân loại chủ đề (tags)")


class FlashcardSet(BaseModel):
    """Tập hợp các Flashcards thuộc một chủ đề."""
    topic: str = Field(..., description="Chủ đề của bộ Flashcards")
    cards: List[FlashcardItem] = Field(..., min_length=1, description="Danh sách các thẻ Flashcards")


class FlashcardGenerationRequest(BaseModel):
    """Yêu cầu tạo bộ Flashcard từ chủ đề hoặc đoạn văn bản."""
    content_or_topic: str = Field(..., min_length=2, description="Chủ đề hoặc đoạn văn bản cần chuyển thành Flashcards")
    num_cards: int = Field(default=5, ge=1, le=30, description="Số lượng thẻ cần tạo (1-30)")
    language: str = Field(default="vi", description="Ngôn ngữ tạo thẻ")
