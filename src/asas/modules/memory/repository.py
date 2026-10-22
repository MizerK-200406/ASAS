"""Long-term Memory Repository providing async SQLite CRUD for student profile, quiz history, and flashcard progress."""

from datetime import datetime
import json
from typing import Any, Dict, List, Optional
import aiosqlite
from asas.modules.memory.db import get_db_connection, init_db
from asas.modules.memory.schemas import (
    FlashcardProgress,
    QuizRecord,
    SM2ReviewResult,
    StudentProfile,
    utc_now,
)


class MemoryRepository:
    """Repository quản lý truy xuất và lưu trữ dữ liệu học sinh trong SQLite async."""

    def __init__(self, db_path: str = "data/asas.db") -> None:
        self.db_path = db_path

    async def initialize(self) -> None:
        """Khởi tạo database schema nếu chưa tồn tại."""
        async with get_db_connection(self.db_path) as db:
            await init_db(db)

    # -------------------------------------------------------------
    # 1. Student Profile
    # -------------------------------------------------------------

    async def get_or_create_student(
        self,
        student_id: str,
        name: str,
        grade_level: Optional[str] = None,
        target_subjects: Optional[List[str]] = None,
    ) -> StudentProfile:
        """Lấy thông tin học sinh theo ID, hoặc tạo mới nếu chưa tồn tại."""
        async with get_db_connection(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM students WHERE student_id = ?", (student_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return StudentProfile(
                        student_id=row["student_id"],
                        name=row["name"],
                        grade_level=row["grade_level"],
                        target_subjects=json.loads(row["target_subjects"]),
                        created_at=datetime.fromisoformat(row["created_at"]),
                    )

            # Tạo mới nếu chưa có
            profile = StudentProfile(
                student_id=student_id,
                name=name,
                grade_level=grade_level,
                target_subjects=target_subjects or [],
            )
            await db.execute(
                """INSERT INTO students (student_id, name, grade_level, target_subjects, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    profile.student_id,
                    profile.name,
                    profile.grade_level,
                    json.dumps(profile.target_subjects),
                    profile.created_at.isoformat(),
                ),
            )
            await db.commit()
            return profile

    # -------------------------------------------------------------
    # 2. Quiz Records & Statistics
    # -------------------------------------------------------------

    async def save_quiz_record(self, record: QuizRecord) -> int:
        """Lưu lại kết quả bài làm Quiz của học sinh."""
        async with get_db_connection(self.db_path) as db:
            cursor = await db.execute(
                """INSERT INTO quiz_records
                   (student_id, topic, score_percentage, total_questions, correct_count, completed_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    record.student_id,
                    record.topic,
                    record.score_percentage,
                    record.total_questions,
                    record.correct_count,
                    record.completed_at.isoformat(),
                ),
            )
            await db.commit()
            return cursor.lastrowid or 0

    async def get_quiz_history(self, student_id: str, limit: int = 10) -> List[QuizRecord]:
        """Lấy danh sách các bài Quiz gần nhất của học sinh."""
        async with get_db_connection(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """SELECT * FROM quiz_records
                   WHERE student_id = ?
                   ORDER BY completed_at DESC, id DESC
                   LIMIT ?""",
                (student_id, limit),
            ) as cursor:
                rows = await cursor.fetchall()
                return [
                    QuizRecord(
                        student_id=row["student_id"],
                        topic=row["topic"],
                        score_percentage=row["score_percentage"],
                        total_questions=row["total_questions"],
                        correct_count=row["correct_count"],
                        completed_at=datetime.fromisoformat(row["completed_at"]),
                    )
                    for row in rows
                ]

    async def get_quiz_statistics(self, student_id: str) -> Dict[str, Any]:
        """Tính toán thống kê điểm số tổng quan của học sinh."""
        async with get_db_connection(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """SELECT COUNT(*) as total_quizzes,
                          AVG(score_percentage) as average_score,
                          SUM(total_questions) as total_questions,
                          SUM(correct_count) as total_correct
                   FROM quiz_records
                   WHERE student_id = ?""",
                (student_id,),
            ) as cursor:
                row = await cursor.fetchone()
                if not row or row["total_quizzes"] == 0:
                    return {
                        "total_quizzes": 0,
                        "average_score": 0.0,
                        "total_questions": 0,
                        "total_correct": 0,
                    }
                return {
                    "total_quizzes": row["total_quizzes"],
                    "average_score": round(row["average_score"], 2),
                    "total_questions": row["total_questions"] or 0,
                    "total_correct": row["total_correct"] or 0,
                }

    # -------------------------------------------------------------
    # 3. Flashcard Progress & Spaced Repetition
    # -------------------------------------------------------------

    async def save_flashcard_progress(self, card: FlashcardProgress) -> FlashcardProgress:
        """Lưu hoặc cập nhật tiến độ học của một Flashcard."""
        async with get_db_connection(self.db_path) as db:
            await db.execute(
                """INSERT INTO flashcard_progress
                   (card_id, student_id, front, back, repetition, interval_days, ease_factor, next_review, last_reviewed)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(card_id) DO UPDATE SET
                       front=excluded.front,
                       back=excluded.back,
                       repetition=excluded.repetition,
                       interval_days=excluded.interval_days,
                       ease_factor=excluded.ease_factor,
                       next_review=excluded.next_review,
                       last_reviewed=excluded.last_reviewed""",
                (
                    card.card_id,
                    card.student_id,
                    card.front,
                    card.back,
                    card.repetition,
                    card.interval_days,
                    card.ease_factor,
                    card.next_review.isoformat(),
                    card.last_reviewed.isoformat() if card.last_reviewed else None,
                ),
            )
            await db.commit()
            return card

    async def get_due_flashcards(
        self,
        student_id: str,
        current_time: Optional[datetime] = None,
        limit: int = 20,
    ) -> List[FlashcardProgress]:
        """Lọc ra các Flashcard đã đến hạn hoặc quá hạn ôn tập tại thời điểm `current_time`."""
        if current_time is None:
            current_time = utc_now()
        iso_time = current_time.isoformat()

        async with get_db_connection(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """SELECT * FROM flashcard_progress
                   WHERE student_id = ? AND next_review <= ?
                   ORDER BY next_review ASC
                   LIMIT ?""",
                (student_id, iso_time, limit),
            ) as cursor:
                rows = await cursor.fetchall()
                return [
                    FlashcardProgress(
                        card_id=row["card_id"],
                        student_id=row["student_id"],
                        front=row["front"],
                        back=row["back"],
                        repetition=row["repetition"],
                        interval_days=row["interval_days"],
                        ease_factor=row["ease_factor"],
                        next_review=datetime.fromisoformat(row["next_review"]),
                        last_reviewed=(
                            datetime.fromisoformat(row["last_reviewed"])
                            if row["last_reviewed"]
                            else None
                        ),
                    )
                    for row in rows
                ]

    async def update_flashcard_review(
        self,
        card_id: str,
        sm2_result: SM2ReviewResult,
        review_time: datetime,
    ) -> Optional[FlashcardProgress]:
        """Cập nhật trạng thái của Flashcard sau khi học sinh trả lời theo kết quả SM-2."""
        async with get_db_connection(self.db_path) as db:
            await db.execute(
                """UPDATE flashcard_progress
                   SET repetition = ?, interval_days = ?, ease_factor = ?, next_review = ?, last_reviewed = ?
                   WHERE card_id = ?""",
                (
                    sm2_result.repetition,
                    sm2_result.interval_days,
                    sm2_result.ease_factor,
                    sm2_result.next_review.isoformat(),
                    review_time.isoformat(),
                    card_id,
                ),
            )
            await db.commit()

            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM flashcard_progress WHERE card_id = ?", (card_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return None
                return FlashcardProgress(
                    card_id=row["card_id"],
                    student_id=row["student_id"],
                    front=row["front"],
                    back=row["back"],
                    repetition=row["repetition"],
                    interval_days=row["interval_days"],
                    ease_factor=row["ease_factor"],
                    next_review=datetime.fromisoformat(row["next_review"]),
                    last_reviewed=(
                        datetime.fromisoformat(row["last_reviewed"])
                        if row["last_reviewed"]
                        else None
                    ),
                )

    async def get_flashcard(self, card_id: str) -> Optional[FlashcardProgress]:
        """Lấy thông tin chi tiết một Flashcard theo card_id."""
        async with get_db_connection(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM flashcard_progress WHERE card_id = ?", (card_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return None
                return FlashcardProgress(
                    card_id=row["card_id"],
                    student_id=row["student_id"],
                    front=row["front"],
                    back=row["back"],
                    repetition=row["repetition"],
                    interval_days=row["interval_days"],
                    ease_factor=row["ease_factor"],
                    next_review=datetime.fromisoformat(row["next_review"]),
                    last_reviewed=(
                        datetime.fromisoformat(row["last_reviewed"])
                        if row["last_reviewed"]
                        else None
                    ),
                )
