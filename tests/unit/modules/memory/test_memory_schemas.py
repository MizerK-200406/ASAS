"""Unit tests for memory schemas and SM-2 data models."""

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from asas.modules.memory.schemas import (
    ChatMessage,
    FlashcardProgress,
    MessageRole,
    QuizRecord,
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
    """Kiểm tra FlashcardProgress với các thông số mặc định."""
    progress = FlashcardProgress(
        card_id="card_101",
        student_id="student_01",
        front="Mặt trước",
        back="Mặt sau",
    )
    assert progress.card_id == "card_101"
    assert progress.student_id == "student_01"
    assert progress.front == "Mặt trước"
    assert progress.back == "Mặt sau"
    assert isinstance(progress.created_at, datetime)


def test_student_profile_extended_fields():
    """Kiểm tra StudentProfile với các trường mở rộng: school, target_goal, learning_style, updated_at."""
    profile = StudentProfile(
        student_id="st_01",
        name="Phạm Dương",
        grade_level="Lớp 12",
        school="THPT Chuyên Hà Nội - Amsterdam",
        target_goal="Đạt 9.0 điểm môn Toán THPTQG",
        learning_style="Socratic, trực quan",
    )
    assert profile.grade_level == "Lớp 12"
    assert profile.school == "THPT Chuyên Hà Nội - Amsterdam"
    assert profile.target_goal == "Đạt 9.0 điểm môn Toán THPTQG"
    assert profile.learning_style == "Socratic, trực quan"
    assert isinstance(profile.updated_at, datetime)


def test_quiz_record_with_ai_feedback():
    """Kiểm tra QuizRecord lưu trữ lời phê và đề xuất cải thiện của AI."""
    record = QuizRecord(
        student_id="st_01",
        topic="Lượng giác",
        score_percentage=66.7,
        total_questions=3,
        correct_count=2,
        ai_praise="Em nắm vững các công thức cộng lượng giác cơ bản.",
        ai_critique="Em còn nhầm dấu ở công thức nhân đôi cos(2x).",
        improvement_plan="Xem lại bảng công thức trang 15 và làm thêm 3 bài tập biến đổi.",
    )
    assert record.ai_praise == "Em nắm vững các công thức cộng lượng giác cơ bản."
    assert record.ai_critique == "Em còn nhầm dấu ở công thức nhân đôi cos(2x)."
    assert record.improvement_plan == "Xem lại bảng công thức trang 15 và làm thêm 3 bài tập biến đổi."


def test_student_activity_log_schema():
    """Kiểm tra StudentActivityLog lưu lại vết hành động học sinh."""
    from asas.modules.memory.schemas import StudentActivityLog

    log = StudentActivityLog(
        id="act_123",
        student_id="st_01",
        action_type="QUIZ_TAKEN",
        description="Hoàn thành bài kiểm tra Lượng giác đạt 66.7%",
    )
    assert log.id == "act_123"
    assert log.student_id == "st_01"
    assert log.action_type == "QUIZ_TAKEN"
    assert log.description == "Hoàn thành bài kiểm tra Lượng giác đạt 66.7%"
    assert isinstance(log.created_at, datetime)


def test_chat_session_and_message_records():
    """Kiểm tra ChatSessionRecord và ChatMessageRecord lưu trữ phiên và tin nhắn bền vững."""
    from asas.modules.memory.schemas import ChatSessionRecord, ChatMessageRecord

    session = ChatSessionRecord(
        id="sess_abc",
        student_id="st_01",
        title="Thảo luận Giải tích và Đạo hàm",
    )
    assert session.id == "sess_abc"
    assert session.student_id == "st_01"
    assert session.title == "Thảo luận Giải tích và Đạo hàm"
    assert isinstance(session.created_at, datetime)

    msg = ChatMessageRecord(
        id=1,
        session_id="sess_abc",
        role="assistant",
        content="Đạo hàm của sin(x) là cos(x).",
        agent_role="tutor",
    )
    assert msg.id == 1
    assert msg.session_id == "sess_abc"
    assert msg.role == "assistant"
    assert msg.agent_role == "tutor"
    assert isinstance(msg.created_at, datetime)


