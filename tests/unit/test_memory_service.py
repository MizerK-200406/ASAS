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
