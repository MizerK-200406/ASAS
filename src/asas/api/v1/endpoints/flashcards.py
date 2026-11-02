from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from asas.api.deps import get_flashcard_service, get_memory_service
from asas.modules.flashcard.schemas import (
    FlashcardGenerationRequest,
    FlashcardItem,
    FlashcardSet,
)
from asas.modules.flashcard.service import FlashcardService
from asas.modules.memory.schemas import FlashcardProgress
from asas.modules.memory.service import MemoryService

router = APIRouter(prefix="/flashcards", tags=["Flashcards"])


class FlashcardGeneratePayload(BaseModel):
    """Payload yêu cầu tạo bộ thẻ ghi nhớ."""
    content_or_topic: str = Field(..., min_length=2, description="Chủ đề hoặc nội dung cần tạo thẻ")
    num_cards: int = Field(default=5, ge=1, le=30, description="Số lượng thẻ cần tạo (1-30)")
    language: str = Field(default="vi", description="Ngôn ngữ tạo thẻ")
    student_id: Optional[str] = Field(None, description="Mã học sinh nếu muốn tự động nạp vào hồ sơ")
    auto_import: bool = Field(default=False, description="Tự động nạp thẻ vào CSDL của học sinh")


class FlashcardGenerateResponse(BaseModel):
    """Kết quả sinh bộ Flashcards và danh sách nạp CSDL (nếu có)."""
    topic: str = Field(..., description="Chủ đề của bộ thẻ")
    cards: List[FlashcardItem] = Field(..., description="Danh sách các thẻ vừa tạo")
    imported_cards: Optional[List[FlashcardProgress]] = Field(
        None,
        description="Danh sách thẻ đã lưu vào hồ sơ của học sinh (nếu auto_import=True)",
    )


class FlashcardImportRequest(BaseModel):
    """Yêu cầu nạp thủ công một bộ FlashcardSet vào tài khoản học sinh."""
    student_id: str = Field(..., description="Mã học sinh")
    card_set: FlashcardSet = Field(..., description="Bộ thẻ FlashcardSet cần nạp")


@router.post(
    "/generate",
    response_model=FlashcardGenerateResponse,
    summary="Tạo bộ thẻ Flashcards AI",
    description="Chuyển đổi chủ đề hoặc tài liệu thành bộ thẻ ghi nhớ chuẩn Active Recall. Tùy chọn nạp ngay vào CSDL.",
)
async def generate_flashcards(
    payload: FlashcardGeneratePayload,
    flashcard_service: FlashcardService = Depends(get_flashcard_service),
    memory_service: MemoryService = Depends(get_memory_service),
) -> FlashcardGenerateResponse:
    gen_request = FlashcardGenerationRequest(
        content_or_topic=payload.content_or_topic,
        num_cards=payload.num_cards,
        language=payload.language,
    )
    flashcard_set = await flashcard_service.generate_flashcards(gen_request)

    imported_cards: Optional[List[FlashcardProgress]] = None
    if payload.auto_import and payload.student_id:
        imported_cards = await memory_service.import_flashcard_set(
            student_id=payload.student_id,
            card_set=flashcard_set,
        )

    return FlashcardGenerateResponse(
        topic=flashcard_set.topic,
        cards=flashcard_set.cards,
        imported_cards=imported_cards,
    )


@router.post(
    "/import",
    response_model=List[FlashcardProgress],
    summary="Nạp bộ FlashcardSet vào học phần của học sinh",
    description="Nạp một tập Flashcards có sẵn vào tài khoản học sinh.",
)
async def import_flashcards(
    payload: FlashcardImportRequest,
    memory_service: MemoryService = Depends(get_memory_service),
) -> List[FlashcardProgress]:
    return await memory_service.import_flashcard_set(
        student_id=payload.student_id,
        card_set=payload.card_set,
    )


@router.get(
    "/student/{student_id}",
    response_model=List[FlashcardProgress],
    summary="Lấy danh sách thẻ Flashcards của học sinh",
    description="Lấy danh sách các Flashcard đã lưu của học sinh.",
)
async def get_student_flashcards(
    student_id: str,
    limit: int = Query(default=50, ge=1, le=100, description="Số lượng thẻ tối đa cần lấy"),
    memory_service: MemoryService = Depends(get_memory_service),
) -> List[FlashcardProgress]:
    return await memory_service.get_student_flashcards(student_id=student_id, limit=limit)
