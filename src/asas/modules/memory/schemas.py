"""Pydantic schemas for memory management, student profile, and flashcards."""

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
    school: Optional[str] = None
    target_subjects: List[str] = Field(default_factory=list)
    target_goal: Optional[str] = None
    learning_style: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class QuizRecord(BaseModel):
    """Bản ghi kết quả bài trắc nghiệm của học sinh kèm nhận xét của AI."""

    id: Optional[int] = None
    student_id: str
    topic: str
    score_percentage: float
    total_questions: int
    correct_count: int
    ai_praise: Optional[str] = None
    ai_critique: Optional[str] = None
    improvement_plan: Optional[str] = None
    completed_at: datetime = Field(default_factory=utc_now)


class StudentActivityLog(BaseModel):
    """Nhật ký hoạt động của học sinh (làm quiz, ôn flashcard, chat trợ lý, dùng tools)."""

    id: str
    student_id: str
    action_type: str
    description: str
    created_at: datetime = Field(default_factory=utc_now)


class ChatSessionRecord(BaseModel):
    """Mô hình dữ liệu lưu trữ một phiên hội thoại học tập trong CSDL SQLite."""

    id: str
    student_id: str
    title: str = "Hội thoại học tập"
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ChatMessageRecord(BaseModel):
    """Bản ghi chi tiết một tin nhắn trong phiên hội thoại được lưu bền vững."""

    id: Optional[int] = None
    session_id: str
    role: str
    content: str
    agent_role: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)


class FlashcardProgress(BaseModel):
    """Trạng thái lưu trữ của một Flashcard trong CSDL của học sinh."""

    card_id: str
    student_id: str
    front: str
    back: str
    created_at: datetime = Field(default_factory=utc_now)
