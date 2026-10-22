"""Unit tests for MemoryRepository using SQLite async operations."""

from datetime import datetime, timedelta, timezone
import pytest
from asas.modules.memory.repository import MemoryRepository
from asas.modules.memory.schemas import FlashcardProgress, QuizRecord, SM2ReviewResult


@pytest.fixture
def repo(tmp_path):
    """Fixture tạo MemoryRepository với database tạm thời tự dọn dẹp sau test."""
    db_file = str(tmp_path / "test_memory.db")
    return MemoryRepository(db_path=db_file)


@pytest.mark.asyncio
async def test_get_or_create_student(repo):
    """Kiểm tra tạo mới học sinh và lấy học sinh đã tồn tại."""
    await repo.initialize()
    # Tạo mới
    student1 = await repo.get_or_create_student(
        student_id="student_01",
        name="Nguyen Van A",
        grade_level="12",
        target_subjects=["Toán", "Tin học"],
    )
    assert student1.student_id == "student_01"
    assert student1.name == "Nguyen Van A"
    assert student1.target_subjects == ["Toán", "Tin học"]

    # Gọi lại với cùng ID -> Phải trả về học sinh cũ
    student2 = await repo.get_or_create_student(
        student_id="student_01",
        name="Ten Khac",
    )
    assert student2.student_id == "student_01"
    assert student2.name == "Nguyen Van A"


@pytest.mark.asyncio
async def test_quiz_record_and_statistics(repo):
    """Kiểm tra lưu lịch sử Quiz và tính toán thống kê điểm số."""
    await repo.initialize()
    await repo.get_or_create_student("student_01", "Nguyen Van A")

    # Lưu 2 bài quiz
    q1 = QuizRecord(
        student_id="student_01",
        topic="Python Cơ bản",
        score_percentage=80.0,
        total_questions=5,
        correct_count=4,
    )
    q2 = QuizRecord(
        student_id="student_01",
        topic="Đại số tuyến tính",
        score_percentage=100.0,
        total_questions=5,
        correct_count=5,
    )

    await repo.save_quiz_record(q1)
    await repo.save_quiz_record(q2)

    # Lấy lịch sử bài làm
    history = await repo.get_quiz_history("student_01")
    assert len(history) == 2
    assert history[0].topic == "Đại số tuyến tính"  # Sắp xếp mới nhất lên đầu
    assert history[1].topic == "Python Cơ bản"

    # Lấy thống kê
    stats = await repo.get_quiz_statistics("student_01")
    assert stats["total_quizzes"] == 2
    assert stats["average_score"] == 90.0
    assert stats["total_questions"] == 10
    assert stats["total_correct"] == 9


@pytest.mark.asyncio
async def test_flashcard_progress_and_due_cards(repo):
    """Kiểm tra lưu flashcard và lọc các thẻ đến hạn ôn tập (Due Cards)."""
    await repo.initialize()
    await repo.get_or_create_student("student_01", "Nguyen Van A")

    now = datetime(2026, 10, 22, 12, 0, 0, tzinfo=timezone.utc)
    past_due = now - timedelta(hours=2)
    future_due = now + timedelta(days=2)

    card_due = FlashcardProgress(
        card_id="card_1",
        student_id="student_01",
        front="1 + 1",
        back="2",
        next_review=past_due,
    )
    card_future = FlashcardProgress(
        card_id="card_2",
        student_id="student_01",
        front="2 + 2",
        back="4",
        next_review=future_due,
    )

    await repo.save_flashcard_progress(card_due)
    await repo.save_flashcard_progress(card_future)

    # Lọc thẻ đến hạn tại thời điểm `now` -> Chỉ được có card_1
    due_cards = await repo.get_due_flashcards("student_01", current_time=now)
    assert len(due_cards) == 1
    assert due_cards[0].card_id == "card_1"

    # Cập nhật kết quả ôn tập SM-2 cho card_1
    sm2_result = SM2ReviewResult(
        repetition=1,
        interval_days=1,
        ease_factor=2.5,
        next_review=now + timedelta(days=1),
    )
    updated_card = await repo.update_flashcard_review(
        card_id="card_1",
        sm2_result=sm2_result,
        review_time=now,
    )
    assert updated_card is not None
    assert updated_card.repetition == 1
    assert updated_card.last_reviewed == now

    # Sau khi cập nhật, card_1 không còn nằm trong danh sách đến hạn tại thời điểm `now`
    due_cards_after = await repo.get_due_flashcards("student_01", current_time=now)
    assert len(due_cards_after) == 0
