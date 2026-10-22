"""Unit tests for SQLite database initialization and schema creation."""

import pytest
import aiosqlite
from asas.modules.memory.db import init_db, get_db_connection


@pytest.mark.asyncio
async def test_init_db_in_memory_creates_tables():
    """Kiểm tra init_db() tạo thành công 3 bảng trong CSDL in-memory."""
    async with aiosqlite.connect(":memory:") as db:
        await init_db(db)

        # Kiểm tra bảng students
        async with db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='students'"
        ) as cursor:
            row = await cursor.fetchone()
            assert row is not None
            assert row[0] == "students"

        # Kiểm tra bảng quiz_records
        async with db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='quiz_records'"
        ) as cursor:
            row = await cursor.fetchone()
            assert row is not None
            assert row[0] == "quiz_records"

        # Kiểm tra bảng flashcard_progress
        async with db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='flashcard_progress'"
        ) as cursor:
            row = await cursor.fetchone()
            assert row is not None
            assert row[0] == "flashcard_progress"


@pytest.mark.asyncio
async def test_foreign_keys_and_schema_constraints():
    """Kiểm tra ràng buộc khóa ngoại (foreign key) hoạt động chính xác."""
    async with aiosqlite.connect(":memory:") as db:
        await db.execute("PRAGMA foreign_keys = ON;")
        await init_db(db)

        # Chèn quiz_record với student_id chưa tồn tại -> Báo lỗi foreign key
        with pytest.raises(aiosqlite.IntegrityError):
            await db.execute(
                """INSERT INTO quiz_records
                   (student_id, topic, score_percentage, total_questions, correct_count, completed_at)
                   VALUES ('non_existent_student', 'Math', 100.0, 5, 5, '2026-10-22T00:00:00Z')"""
            )
            await db.commit()
