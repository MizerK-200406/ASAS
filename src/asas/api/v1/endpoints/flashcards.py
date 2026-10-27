from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
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

router = APIRouter(prefix="/flashcards", tags=["Flashcards & SM-2"])


class FlashcardGeneratePayload(BaseModel):
    """Payload yêu cầu tạo bộ thẻ ghi nhớ."""
    content_or_topic: str = Field(..., min_length=2, description="Chủ đề hoặc nội dung cần tạo thẻ")
    num_cards: int = Field(default=5, ge=1, le=30, description="Số lượng thẻ cần tạo (1-30)")
    language: str = Field(default="vi", description="Ngôn ngữ tạo thẻ")
    student_id: Optional[str] = Field(None, description="Mã học sinh nếu muốn tự động nạp vào hệ thống SM-2")
    auto_import: bool = Field(default=False, description="Tự động nạp thẻ vào CSDL ôn tập")


class FlashcardGenerateResponse(BaseModel):
    """Kết quả sinh bộ Flashcards và danh sách nạp CSDL (nếu có)."""
    topic: str = Field(..., description="Chủ đề của bộ thẻ")
    cards: List[FlashcardItem] = Field(..., description="Danh sách các thẻ vừa tạo")
    imported_cards: Optional[List[FlashcardProgress]] = Field(
        None,
        description="Danh sách thẻ đã lưu vào tiến trình ôn tập của học sinh (nếu auto_import=True)",
    )


class FlashcardReviewRequest(BaseModel):
    """Đánh giá chất lượng nhớ của thẻ theo thang điểm SuperMemo SM-2 (0-5)."""
    card_id: str = Field(..., description="Mã định danh của thẻ")
    quality: int = Field(
        ...,
        ge=0,
        le=5,
        description="Chất lượng nhớ từ 0 (hoàn toàn quên) đến 5 (nhớ hoàn hảo tức thì)",
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
    description="Nạp một tập Flashcards có sẵn vào hàng đợi ôn tập lặp lại ngắt quãng (SM-2) của học sinh.",
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
    "/due",
    response_model=List[FlashcardProgress],
    summary="Lấy các thẻ đến hạn ôn tập",
    description="Lấy danh sách các Flashcard đã đến hạn ôn tập (Spaced Repetition) theo thuật toán SM-2.",
)
async def get_due_flashcards(
    student_id: str = Query(..., description="Mã học sinh"),
    limit: int = Query(default=20, ge=1, le=100, description="Số lượng thẻ tối đa cần lấy"),
    memory_service: MemoryService = Depends(get_memory_service),
) -> List[FlashcardProgress]:
    return await memory_service.get_due_flashcards(student_id=student_id, limit=limit)


@router.post(
    "/review",
    response_model=FlashcardProgress,
    summary="Ghi nhận kết quả ôn tập thẻ (SM-2)",
    description="Cập nhật tiến độ ôn tập thẻ theo thang điểm 0-5 và tự động tính lịch ôn tập kế tiếp.",
)
async def review_flashcard(
    payload: FlashcardReviewRequest,
    memory_service: MemoryService = Depends(get_memory_service),
) -> FlashcardProgress:
    try:
        return await memory_service.review_flashcard(
            card_id=payload.card_id,
            quality=payload.quality,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
