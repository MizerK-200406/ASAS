"""Unit tests for MemoryService orchestrating session memory, repository, and SM-2."""

import pytest
from asas.modules.flashcard.schemas import FlashcardItem, FlashcardSet
from asas.modules.memory.service import MemoryService


@pytest.fixture
def memory_service(tmp_path):
    """Fixture tạo MemoryService với database SQLite tạm."""
    db_file = str(tmp_path / "test_memory_service.db")
    return MemoryService(db_path=db_file)


@pytest.mark.asyncio
async def test_session_management(memory_service):
    """Kiểm tra quản lý phiên hội thoại ngắn hạn qua MemoryService."""
    sess = memory_service.get_or_create_session(
        session_id="session_test",
        system_prompt="Bạn là gia sư",
        max_messages=5,
    )
    sess.add_message("user", "Xin chào")

    same_sess = memory_service.get_session("session_test")
    assert same_sess is not None
    assert len(same_sess.get_messages()) == 1


@pytest.mark.asyncio
async def test_quiz_and_student_summary(memory_service):
    """Kiểm tra ghi nhận kết quả bài kiểm tra và tổng hợp báo cáo học sinh."""
    await memory_service.initialize()
    await memory_service.get_or_create_student("st_01", "Trần Văn B")

    await memory_service.record_quiz_result(
        student_id="st_01",
        topic="Đại số",
        score_percentage=100.0,
        total_questions=5,
        correct_count=5,
    )

    summary = await memory_service.get_student_summary("st_01")
    assert summary["profile"].name == "Trần Văn B"
    assert summary["quiz_stats"]["total_quizzes"] == 1
    assert summary["quiz_stats"]["average_score"] == 100.0
    assert len(summary["recent_quizzes"]) == 1


@pytest.mark.asyncio
async def test_flashcard_sm2_review_flow(memory_service):
    """Kiểm tra chu trình nạp Flashcard từ FlashcardSet và ôn tập theo SM-2."""
    await memory_service.initialize()
    await memory_service.get_or_create_student("st_01", "Trần Văn B")

    # Giả lập FlashcardSet vừa sinh từ FlashcardService
    cards = [
        FlashcardItem(front="CPU là gì?", back="Central Processing Unit", tags=["CS"]),
        FlashcardItem(front="RAM là gì?", back="Random Access Memory", tags=["CS"]),
    ]
    card_set = FlashcardSet(topic="Phần cứng máy tính", cards=cards)

    # Nạp thẻ vào bộ nhớ
    saved_cards = await memory_service.import_flashcard_set("st_01", card_set)
    assert len(saved_cards) == 2

    # Lấy các thẻ cần ôn tập ngay
    due_cards = await memory_service.get_due_flashcards("st_01")
    assert len(due_cards) == 2

    # Học sinh ôn thẻ đầu tiên và đánh giá quality = 5 (nhớ hoàn hảo)
    card_to_review = due_cards[0]
    updated_card = await memory_service.review_flashcard(
        card_id=card_to_review.card_id,
        quality=5,
    )
    assert updated_card.repetition == 1
    assert updated_card.interval_days == 1
    assert updated_card.ease_factor > 2.5


@pytest.mark.asyncio
async def test_record_quiz_with_ai_feedback_and_activity_log(memory_service):
    """Kiểm tra ghi nhận Quiz kèm nhận xét AI và tự động lưu Activity Log."""
    await memory_service.initialize()
    await memory_service.get_or_create_student("st_phamd", "Phạm Dương", grade_level="Lớp 12")

    await memory_service.record_quiz_result(
        student_id="st_phamd",
        topic="Lượng giác",
        score_percentage=80.0,
        total_questions=5,
        correct_count=4,
        ai_praise="Rất tốt ở các công thức biến đổi tích thành tổng.",
        ai_critique="Cần chú ý điều kiện của tan(x).",
        improvement_plan="Làm thêm 2 bài tập điều kiện xác định.",
    )

    summary = await memory_service.get_student_summary("st_phamd")
    recent = summary["recent_quizzes"][0]
    assert recent.ai_praise == "Rất tốt ở các công thức biến đổi tích thành tổng."
    assert recent.ai_critique == "Cần chú ý điều kiện của tan(x)."
    assert recent.improvement_plan == "Làm thêm 2 bài tập điều kiện xác định."

    # Kiểm tra activity log tự động được ghi lại
    logs = summary.get("recent_activities", [])
    assert len(logs) >= 1
    assert logs[0].action_type == "QUIZ_COMPLETED"
    assert "Lượng giác" in logs[0].description


@pytest.mark.asyncio
async def test_get_all_students_and_quiz_detail(memory_service):
    """Kiểm tra MemoryService cung cấp danh sách học sinh và chi tiết bài quiz."""
    await memory_service.initialize()
    await memory_service.get_or_create_student("st_user1", "Nguyễn Duy Long", grade_level="Lớp 10")
    await memory_service.get_or_create_student("st_user2", "Nguyễn Duy Long", grade_level="Lớp 12")

    students = await memory_service.get_all_students()
    assert len(students) >= 2

    quiz_id = await memory_service.record_quiz_result(
        student_id="st_user1",
        topic="Cơ bản",
        score_percentage=100.0,
        total_questions=2,
        correct_count=2,
        ai_praise="Rất tốt!",
    )

    detail = await memory_service.get_quiz_record_by_id(quiz_id)
    assert detail is not None
    assert detail.id == quiz_id
    assert detail.ai_praise == "Rất tốt!"


@pytest.mark.asyncio
async def test_persistent_chat_service_and_expanded_activity_stream(memory_service):
    """Kiểm tra MemoryService lưu trữ phiên chat bền vững và mở rộng activity stream lên 10 mục."""
    await memory_service.initialize()
    await memory_service.get_or_create_student("st_user1", "Nguyễn Duy Long")

    # Tạo phiên chat
    session = await memory_service.get_or_create_persistent_session(
        session_id="sess_physics_01",
        student_id="st_user1",
        title="Ôn tập Định luật Newton",
    )
    assert session.id == "sess_physics_01"

    # Lưu tin nhắn
    await memory_service.save_chat_message(
        session_id="sess_physics_01",
        role="user",
        content="Định luật 2 Newton phát biểu thế nào?",
    )
    await memory_service.save_chat_message(
        session_id="sess_physics_01",
        role="assistant",
        content="Gia tốc của một vật tỉ lệ thuận với lực tác dụng: F = m * a.",
        agent_role="tutor",
    )

    messages = await memory_service.get_session_chat_messages("sess_physics_01")
    assert len(messages) == 2
    assert messages[0].content == "Định luật 2 Newton phát biểu thế nào?"
    assert messages[1].agent_role == "tutor"

    # Thêm 10 hoạt động khác nhau
    for i in range(10):
        await memory_service.log_activity(
            student_id="st_user1",
            action_type=f"ACTION_{i}",
            description=f"Mô tả hoạt động số {i}",
        )

    summary = await memory_service.get_student_summary("st_user1")
    assert len(summary["recent_activities"]) == 10



