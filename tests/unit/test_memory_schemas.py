"""Unit tests for memory schemas and SM-2 data models."""

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from asas.modules.memory.schemas import (
    ChatMessage,
    FlashcardProgress,
    MessageRole,
    QuizRecord,
    SM2ReviewInput,
    SM2ReviewResult,
    StudentProfile,
)


def test_chat_message_schema():
    """Kiểm tra ChatMessage khởi tạo hợp lệ và hỗ trợ enum role."""
    msg = ChatMessage(role=MessageRole.USER, content="Xin chào AI!")
    assert msg.role == MessageRole.USER
    assert msg.content == "Xin chào AI!"
    assert isinstance(msg.timestamp, datetime)

    # Chấp nhận chuỗi string hợp lệ
    msg2 = ChatMessage(role="assistant", content="Chào bạn!")
    assert msg2.role == MessageRole.ASSISTANT


def test_student_profile_schema():
    """Kiểm tra StudentProfile với giá trị mặc định."""
    profile = StudentProfile(student_id="student_01", name="Nguyen Van A")
    assert profile.student_id == "student_01"
    assert profile.name == "Nguyen Van A"
    assert profile.target_subjects == []
    assert isinstance(profile.created_at, datetime)


def test_quiz_record_schema():
    """Kiểm tra QuizRecord lưu trữ kết quả bài trắc nghiệm."""
    record = QuizRecord(
        student_id="student_01",
        topic="Python Basics",
        score_percentage=80.0,
        total_questions=5,
        correct_count=4,
    )
    assert record.score_percentage == 80.0
    assert record.correct_count == 4
    assert record.total_questions == 5


def test_flashcard_progress_defaults():
    """Kiểm tra FlashcardProgress với các thông số SM-2 mặc định."""
    progress = FlashcardProgress(
        card_id="card_101",
        student_id="student_01",
        front="Mặt trước",
        back="Mặt sau",
    )
    assert progress.repetition == 0
    assert progress.interval_days == 1
    assert progress.ease_factor == 2.5
    assert progress.last_reviewed is None
    assert isinstance(progress.next_review, datetime)


def test_sm2_review_input_validation():
    """Kiểm tra SM2ReviewInput validate chặt chẽ thang điểm quality 0..5 và ease_factor >= 1.3."""
    # Hợp lệ
    valid_input = SM2ReviewInput(quality=4, repetition=1, interval_days=6, ease_factor=2.5)
    assert valid_input.quality == 4

    # Quality < 0 -> Báo lỗi
    with pytest.raises(ValidationError):
        SM2ReviewInput(quality=-1)

    # Quality > 5 -> Báo lỗi
    with pytest.raises(ValidationError):
        SM2ReviewInput(quality=6)

    # Ease factor < 1.3 -> Báo lỗi
    with pytest.raises(ValidationError):
        SM2ReviewInput(quality=5, ease_factor=1.2)


def test_sm2_review_result():
    """Kiểm tra SM2ReviewResult lưu kết quả sau khi tính toán SM-2."""
    now = datetime.now(timezone.utc)
    result = SM2ReviewResult(
        repetition=2,
        interval_days=6,
        ease_factor=2.6,
        next_review=now,
    )
    assert result.repetition == 2
    assert result.interval_days == 6
    assert result.ease_factor == 2.6
    assert result.next_review == now
