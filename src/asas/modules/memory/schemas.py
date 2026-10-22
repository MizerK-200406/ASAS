"""Pydantic schemas for memory management, student profile, and SM-2 spaced repetition."""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


def utc_now() -> datetime:
    """Helper trả về thời gian hiện tại chuẩn UTC."""
    return datetime.now(timezone.utc)


class MessageRole(str, Enum):
    """Vai trò của đối tượng gửi tin nhắn trong hội thoại."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class ChatMessage(BaseModel):
    """Mô hình dữ liệu cho một tin nhắn trong bộ nhớ phiên (Session Memory)."""

    role: MessageRole
    content: str
    timestamp: datetime = Field(default_factory=utc_now)


class StudentProfile(BaseModel):
    """Hồ sơ thông tin học sinh được lưu trữ dài hạn."""

    student_id: str
    name: str
    grade_level: Optional[str] = None
    target_subjects: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)


class QuizRecord(BaseModel):
    """Bản ghi kết quả bài trắc nghiệm của học sinh."""

    student_id: str
    topic: str
    score_percentage: float
    total_questions: int
    correct_count: int
    completed_at: datetime = Field(default_factory=utc_now)


class FlashcardProgress(BaseModel):
    """Trạng thái học tập và hẹn lịch ôn tập của một Flashcard theo thuật toán SM-2."""

    card_id: str
    student_id: str
    front: str
    back: str
    repetition: int = 0
    interval_days: int = 1
    ease_factor: float = 2.5
    next_review: datetime = Field(default_factory=utc_now)
    last_reviewed: Optional[datetime] = None


class SM2ReviewInput(BaseModel):
    """Dữ liệu đầu vào để tính toán thuật toán SuperMemo SM-2 sau mỗi lần lật thẻ."""

    quality: int = Field(ge=0, le=5, description="Chất lượng nhớ từ 0 (quên sạch) đến 5 (nhớ hoàn hảo)")
    repetition: int = Field(ge=0, default=0, description="Số lần ôn tập thành công liên tiếp")
    interval_days: int = Field(ge=1, default=1, description="Khoảng cách ngày ôn tập hiện tại")
    ease_factor: float = Field(ge=1.3, default=2.5, description="Hệ số độ dễ (tối thiểu 1.3)")


class SM2ReviewResult(BaseModel):
    """Kết quả tính toán sau khi áp dụng thuật toán SuperMemo SM-2."""

    repetition: int
    interval_days: int
    ease_factor: float
    next_review: datetime
