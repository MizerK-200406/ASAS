from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from asas.api.deps import get_memory_service
from asas.modules.memory.service import MemoryService
from asas.modules.memory.schemas import (
    StudentProfile,
    StudentActivityLog,
    QuizRecord,
)

router = APIRouter(prefix="/students", tags=["Students"])


class StudentCreateOrUpdateRequest(BaseModel):
    student_id: str = Field(..., min_length=2, max_length=50, description="Mã định danh hoặc Username")
    name: str = Field(..., min_length=1, max_length=100, description="Họ và tên học sinh")
    grade_level: Optional[str] = Field(None, max_length=50, description="Khối lớp (VD: Lớp 12)")
    school: Optional[str] = Field(None, max_length=100, description="Trường học")
    target_subjects: List[str] = Field(default_factory=list, description="Danh sách môn học mục tiêu")
    target_goal: Optional[str] = Field(None, max_length=500, description="Mục tiêu học tập")
    learning_style: Optional[str] = Field(None, max_length=100, description="Phong cách học tập")


class StudentSummaryResponse(BaseModel):
    profile: StudentProfile
    quiz_stats: Dict[str, Any]
    recent_quizzes: List[QuizRecord]
    recent_activities: List[StudentActivityLog]


@router.get("", response_model=List[StudentProfile])
async def list_students(
    memory_service: MemoryService = Depends(get_memory_service),
) -> List[StudentProfile]:
    """Lấy danh sách tất cả học sinh đã lưu trong cơ sở dữ liệu."""
    return await memory_service.get_all_students()


@router.post("", response_model=StudentProfile)
async def create_or_update_student(
    payload: StudentCreateOrUpdateRequest,
    memory_service: MemoryService = Depends(get_memory_service),
) -> StudentProfile:
    """Tạo mới hoặc cập nhật hồ sơ học sinh."""
    return await memory_service.get_or_create_student(
        student_id=payload.student_id,
        name=payload.name,
        grade_level=payload.grade_level,
        school=payload.school,
        target_subjects=payload.target_subjects,
        target_goal=payload.target_goal,
        learning_style=payload.learning_style,
    )


@router.get("/{student_id}", response_model=StudentSummaryResponse)
async def get_student_detail(
    student_id: str,
    memory_service: MemoryService = Depends(get_memory_service),
) -> StudentSummaryResponse:
    """Lấy thông tin chi tiết hồ sơ kèm thống kê kết quả học tập."""
    existing_students = await memory_service.get_all_students()
    if not any(st.student_id == student_id for st in existing_students):
        raise HTTPException(status_code=404, detail=f"Không tìm thấy học sinh với ID '{student_id}'.")

    summary = await memory_service.get_student_summary(student_id)
    return StudentSummaryResponse(**summary)


@router.get("/{student_id}/activities", response_model=List[StudentActivityLog])
async def get_student_activities(
    student_id: str,
    limit: int = Query(default=50, ge=1, le=200, description="Số lượng bản ghi tối đa"),
    memory_service: MemoryService = Depends(get_memory_service),
) -> List[StudentActivityLog]:
    """Lấy dòng sự kiện hoạt động hợp nhất của học sinh (Quiz, SM-2, Chat)."""
    return await memory_service.get_student_activity_logs(student_id=student_id, limit=limit)


@router.get("/{student_id}/quiz-records/{record_id}", response_model=QuizRecord)
async def get_student_quiz_record(
    student_id: str,
    record_id: int,
    memory_service: MemoryService = Depends(get_memory_service),
) -> QuizRecord:
    """Xem chi tiết một bài thi trắc nghiệm (bao gồm các câu hỏi, đáp án và nhận xét AI)."""
    record = await memory_service.get_quiz_record_by_id(record_id)
    if not record or record.student_id != student_id:
        raise HTTPException(
            status_code=404,
            detail=f"Không tìm thấy bài thi #{record_id} của học sinh '{student_id}'.",
        )
    return record
