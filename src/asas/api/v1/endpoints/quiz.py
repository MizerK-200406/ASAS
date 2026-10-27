from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from asas.api.deps import get_memory_service, get_quiz_service
from asas.modules.memory.service import MemoryService
from asas.modules.quiz.schemas import (
    Quiz,
    QuizGenerationRequest,
    QuizGradeResult,
)
from asas.modules.quiz.service import QuizService

router = APIRouter(prefix="/quiz", tags=["Quiz"])


class QuizGradeSubmission(BaseModel):
    """Payload gửi bài làm trắc nghiệm để chấm điểm."""
    quiz: Quiz = Field(..., description="Bộ đề trắc nghiệm đã làm")
    user_answers: Dict[int, str] = Field(
        ...,
        description="Bản đồ các câu trả lời của học sinh: {question_index: chosen_option_id}",
    )
    student_id: Optional[str] = Field(
        None,
        description="Mã học sinh (nếu muốn lưu kết quả vào lịch sử học tập)",
    )


class QuizGradingResponse(BaseModel):
    """Kết quả chấm điểm bài trắc nghiệm trả về cho client."""
    total_questions: int = Field(..., description="Tổng số câu hỏi")
    correct_count: int = Field(..., description="Số câu trả lời đúng")
    score_percentage: float = Field(..., description="Tỷ lệ điểm phần trăm (0 - 100)")
    details: List[Dict[str, Any]] = Field(default_factory=list, description="Chi tiết từng câu hỏi")
    record_id: Optional[int] = Field(None, description="Mã bản ghi lịch sử quiz trong CSDL nếu đã lưu")


@router.post(
    "/generate",
    response_model=Quiz,
    summary="Tạo đề trắc nghiệm AI",
    description="Tạo bộ câu hỏi trắc nghiệm chất lượng cao từ LLM dựa trên chủ đề, số câu và độ khó.",
)
async def generate_quiz(
    request: QuizGenerationRequest,
    quiz_service: QuizService = Depends(get_quiz_service),
) -> Quiz:
    try:
        return await quiz_service.generate_quiz(request)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi tạo đề trắc nghiệm: {str(e)}",
        )


@router.post(
    "/grade",
    response_model=QuizGradingResponse,
    summary="Chấm điểm bài trắc nghiệm",
    description="Chấm điểm tất định bài làm của học sinh và tùy chọn lưu vào hồ sơ học tập.",
)
async def grade_quiz(
    submission: QuizGradeSubmission,
    quiz_service: QuizService = Depends(get_quiz_service),
    memory_service: MemoryService = Depends(get_memory_service),
) -> QuizGradingResponse:
    grade_result: QuizGradeResult = quiz_service.grade_quiz(
        quiz=submission.quiz,
        user_answers=submission.user_answers,
    )

    record_id: Optional[int] = None
    if submission.student_id:
        record_id = await memory_service.record_quiz_result(
            student_id=submission.student_id,
            topic=submission.quiz.topic,
            score_percentage=grade_result.score_percentage,
            total_questions=grade_result.total_questions,
            correct_count=grade_result.correct_count,
        )

    return QuizGradingResponse(
        total_questions=grade_result.total_questions,
        correct_count=grade_result.correct_count,
        score_percentage=grade_result.score_percentage,
        details=grade_result.details,
        record_id=record_id,
    )
