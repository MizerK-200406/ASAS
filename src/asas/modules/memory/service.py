"""MemoryService orchestrating conversational session memory, SQLite persistence, and SM-2 spaced repetition."""

from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid
from loguru import logger

from asas.modules.flashcard.schemas import FlashcardSet
from asas.modules.memory.repository import MemoryRepository
from asas.modules.memory.schemas import (
    FlashcardProgress,
    QuizRecord,
    SM2ReviewInput,
    StudentProfile,
    utc_now,
)
from asas.modules.memory.session import SessionMemory
from asas.modules.memory.sm2 import calculate_sm2


class MemoryService:
    """Service trung tâm điều phối toàn diện hệ thống bộ nhớ cho AI Study Assistant."""

    def __init__(self, db_path: str = "data/asas.db") -> None:
        self.repository = MemoryRepository(db_path=db_path)
        self._sessions: Dict[str, SessionMemory] = {}

    async def initialize(self) -> None:
        """Khởi tạo database schema nếu chưa tồn tại."""
        await self.repository.initialize()

    # -------------------------------------------------------------
    # 1. Quản lý Session Memory (Bộ nhớ hội thoại ngắn hạn)
    # -------------------------------------------------------------

    def get_or_create_session(
        self,
        session_id: Optional[str] = None,
        system_prompt: Optional[str] = None,
        max_messages: int = 10,
    ) -> SessionMemory:
        """Lấy hoặc tạo mới một phiên hội thoại có quản lý sliding window."""
        sess_id = session_id or str(uuid.uuid4())
        if sess_id not in self._sessions:
            self._sessions[sess_id] = SessionMemory(
                session_id=sess_id,
                system_prompt=system_prompt,
                max_messages=max_messages,
            )
        return self._sessions[sess_id]

    def get_session(self, session_id: str) -> Optional[SessionMemory]:
        """Lấy phiên hội thoại theo session_id."""
        return self._sessions.get(session_id)

    # -------------------------------------------------------------
    # 2. Quản lý Hồ sơ học sinh & Lịch sử học tập
    # -------------------------------------------------------------

    async def get_or_create_student(
        self,
        student_id: str,
        name: str,
        grade_level: Optional[str] = None,
        target_subjects: Optional[List[str]] = None,
    ) -> StudentProfile:
        """Lấy hoặc tạo mới hồ sơ học sinh."""
        return await self.repository.get_or_create_student(
            student_id=student_id,
            name=name,
            grade_level=grade_level,
            target_subjects=target_subjects,
        )

    async def record_quiz_result(
        self,
        student_id: str,
        topic: str,
        score_percentage: float,
        total_questions: int,
        correct_count: int,
    ) -> int:
        """Ghi nhận kết quả làm bài trắc nghiệm của học sinh vào CSDL."""
        record = QuizRecord(
            student_id=student_id,
            topic=topic,
            score_percentage=score_percentage,
            total_questions=total_questions,
            correct_count=correct_count,
        )
        return await self.repository.save_quiz_record(record)

    async def get_student_summary(self, student_id: str) -> Dict[str, Any]:
        """Tổng hợp thông tin hồ sơ, thống kê điểm số và các bài kiểm tra gần nhất."""
        profile = await self.repository.get_or_create_student(
            student_id=student_id,
            name="Học sinh",
        )
        quiz_stats = await self.repository.get_quiz_statistics(student_id)
        recent_quizzes = await self.repository.get_quiz_history(student_id, limit=5)
        return {
            "profile": profile,
            "quiz_stats": quiz_stats,
            "recent_quizzes": recent_quizzes,
        }

    # -------------------------------------------------------------
    # 3. Quản lý Flashcard & Ôn tập Spaced Repetition (SM-2)
    # -------------------------------------------------------------

    async def import_flashcard_set(
        self,
        student_id: str,
        card_set: FlashcardSet,
    ) -> List[FlashcardProgress]:
        """Nạp toàn bộ thẻ từ một FlashcardSet vào hệ thống hẹn lịch SM-2."""
        saved_cards: List[FlashcardProgress] = []
        for card_item in card_set.cards:
            card_id = f"card_{uuid.uuid4().hex[:8]}"
            progress = FlashcardProgress(
                card_id=card_id,
                student_id=student_id,
                front=card_item.front,
                back=card_item.back,
            )
            saved = await self.repository.save_flashcard_progress(progress)
            saved_cards.append(saved)

        logger.info(f"Đã nạp thành công {len(saved_cards)} thẻ cho học sinh {student_id}")
        return saved_cards

    async def get_due_flashcards(
        self,
        student_id: str,
        current_time: Optional[datetime] = None,
        limit: int = 20,
    ) -> List[FlashcardProgress]:
        """Lấy danh sách các thẻ cần ôn tập hôm nay."""
        return await self.repository.get_due_flashcards(
            student_id=student_id,
            current_time=current_time,
            limit=limit,
        )

    async def review_flashcard(
        self,
        card_id: str,
        quality: int,
        review_time: Optional[datetime] = None,
    ) -> FlashcardProgress:
        """Ghi nhận đánh giá của học sinh (quality 0..5) và tính toán lịch ôn tập mới bằng SM-2."""
        if review_time is None:
            review_time = utc_now()

        card = await self.repository.get_flashcard(card_id)
        if not card:
            raise ValueError(f"Không tìm thấy thẻ Flashcard với mã: {card_id}")

        sm2_input = SM2ReviewInput(
            quality=quality,
            repetition=card.repetition,
            interval_days=card.interval_days,
            ease_factor=card.ease_factor,
        )
        sm2_result = calculate_sm2(sm2_input, review_datetime=review_time)

        updated_card = await self.repository.update_flashcard_review(
            card_id=card_id,
            sm2_result=sm2_result,
            review_time=review_time,
        )
        if not updated_card:
            raise RuntimeError(f"Lỗi không thể cập nhật Flashcard: {card_id}")

        return updated_card
