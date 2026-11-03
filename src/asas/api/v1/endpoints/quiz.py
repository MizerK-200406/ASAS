from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from pydantic import BaseModel, Field

from asas.core.llm_client import LLMClientError, LLMParseError
from asas.api.deps import get_memory_service, get_quiz_service
from asas.modules.agents.schemas import EvaluationResult
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
    evaluate_with_agent: bool = Field(
        default=True,
        description="Kích hoạt EvaluatorAgent phân tích lỗ hổng kiến thức và đưa ra lời khuyên",
    )


class QuizGradingResponse(BaseModel):
    """Kết quả chấm điểm bài trắc nghiệm kèm đánh giá từ Evaluator Agent và telemetry."""
    total_questions: int = Field(..., description="Tổng số câu hỏi")
    correct_count: int = Field(..., description="Số câu trả lời đúng")
    score_percentage: float = Field(..., description="Tỷ lệ điểm phần trăm (0 - 100)")
    details: List[Dict[str, Any]] = Field(default_factory=list, description="Chi tiết từng câu hỏi kèm ngộ nhận nếu có")
    record_id: Optional[int] = Field(None, description="Mã bản ghi lịch sử quiz trong CSDL nếu đã lưu")
    evaluation: Optional[EvaluationResult] = Field(
        None,
        description="Đánh giá sư phạm chuyên sâu từ Evaluator Agent (lỗ hổng kiến thức, điểm mạnh, lời khuyên)",
    )
    duration_ms: Optional[float] = Field(None, description="Thời gian thực thi đánh giá (ms)")
    total_tokens: Optional[int] = Field(None, description="Tổng số token đã sử dụng")
    source: str = Field(default="ai_generated", description="Nguồn gốc đề thi ('bank' hoặc 'ai_generated')")


@router.post(
    "/generate",
    response_model=Quiz,
    summary="Tạo đề trắc nghiệm AI (Hybrid Question Bank)",
    description="Ưu tiên lấy đề từ kho câu hỏi CSDL (siêu tốc, 0 token) hoặc gọi LLM sinh mới khi có yêu cầu.",
)
async def generate_quiz(
    request: QuizGenerationRequest,
    quiz_service: QuizService = Depends(get_quiz_service),
) -> Quiz:
    try:
        return await quiz_service.generate_quiz(request)
    except LLMParseError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Mô hình AI phản hồi dữ liệu không chuẩn hoặc chạm giới hạn token: {str(e)}. Hãy thử lại hoặc giảm số lượng câu hỏi.",
        )
    except LLMClientError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Dịch vụ AI hiện không khả dụng: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi tạo đề trắc nghiệm: {str(e)}",
        )


@router.post(
    "/grade",
    response_model=QuizGradingResponse,
    summary="Chấm điểm & Đánh giá bài trắc nghiệm với AI Agent",
    description="Chấm điểm tất định, nhận diện ngộ nhận (misconceptions) và kích hoạt EvaluatorAgent phân tích lỗ hổng kiến thức.",
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

    evaluation: Optional[EvaluationResult] = None
    if submission.evaluate_with_agent:
        try:
            student_name: Optional[str] = None
            if submission.student_id:
                profile = await memory_service.get_student_profile(submission.student_id)
                if profile:
                    student_name = profile.name

            evaluation = await quiz_service.evaluate_quiz_with_agent(
                quiz=submission.quiz,
                user_answers=submission.user_answers,
                grade_result=grade_result,
                student_name=student_name,
            )
        except Exception as e:
            # Fallback nhẹ nhàng nếu agent gặp sự cố kết nối
            evaluation = EvaluationResult(
                score_summary=f"Đạt {grade_result.correct_count}/{grade_result.total_questions} ({grade_result.score_percentage}%)",
                strengths=["Đã hoàn thành bài kiểm tra"],
                knowledge_gaps=grade_result.misconceptions,
                critique=f"Chưa thể tạo đánh giá chi tiết do lỗi kết nối: {e}",
                recommendations=["Hãy xem lại các câu làm sai trong phần chi tiết"],
                improvement_plan=None,
            )

    # Lấy telemetry từ lần gọi LLM gần nhất (nếu có)
    exec_record = getattr(quiz_service.llm_client, "last_execution_record", None)
    duration_ms = exec_record.latency.duration_ms if exec_record else 0.0
    prompt_tokens = exec_record.tokens.prompt_tokens if exec_record else 0
    completion_tokens = exec_record.tokens.completion_tokens if exec_record else 0
    total_tokens = exec_record.tokens.total_tokens if exec_record else 0

    record_id: Optional[int] = None
    if submission.student_id:
        # Tự động đảm bảo student_id tồn tại để ngăn chặn triệt để lỗi ForeignKeyViolationError
        existing_profile = await memory_service.get_student_profile(submission.student_id)
        if not existing_profile:
            logger.warning(
                f"student_id '{submission.student_id}' chưa có hồ sơ trong database. Tự động khởi tạo hồ sơ dự phòng..."
            )
            await memory_service.get_or_create_student(
                student_id=submission.student_id,
                name=f"Học sinh ({submission.student_id})",
            )

        praise_str = ", ".join(evaluation.strengths) if evaluation and evaluation.strengths else None
        critique_str = evaluation.critique if evaluation else None
        plan_str = (
            evaluation.improvement_plan or (", ".join(evaluation.recommendations) if evaluation.recommendations else None)
            if evaluation else None
        )

        try:
            record_id = await memory_service.record_quiz_result(
                student_id=submission.student_id,
                topic=submission.quiz.topic,
                score_percentage=grade_result.score_percentage,
                total_questions=grade_result.total_questions,
                correct_count=grade_result.correct_count,
                ai_praise=praise_str,
                ai_critique=critique_str,
                improvement_plan=plan_str,
                duration_ms=duration_ms,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
            )
        except Exception as e:
            logger.error(f"Không thể lưu kết quả bài thi vào database: {e}")

    return QuizGradingResponse(
        total_questions=grade_result.total_questions,
        correct_count=grade_result.correct_count,
        score_percentage=grade_result.score_percentage,
        details=grade_result.details,
        record_id=record_id,
        evaluation=evaluation,
        duration_ms=duration_ms if exec_record else None,
        total_tokens=total_tokens if exec_record else None,
        source=submission.quiz.source,
    )
