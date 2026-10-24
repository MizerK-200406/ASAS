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

        # Kiểm tra bảng mới student_activity_logs
        async with db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='student_activity_logs'"
        ) as cursor:
            row = await cursor.fetchone()
            assert row is not None
            assert row[0] == "student_activity_logs"

        # Kiểm tra bảng chat_sessions và chat_messages bền vững
        async with db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='chat_sessions'"
        ) as cursor:
            row = await cursor.fetchone()
            assert row is not None
            assert row[0] == "chat_sessions"

        async with db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='chat_messages'"
        ) as cursor:
            row = await cursor.fetchone()
            assert row is not None
            assert row[0] == "chat_messages"

        # Kiểm tra các cột mở rộng của students
        async with db.execute("PRAGMA table_info(students)") as cursor:
            columns = [c[1] for c in await cursor.fetchall()]
            for col in ["school", "target_goal", "learning_style", "updated_at"]:
                assert col in columns

        # Kiểm tra các cột lời phê AI của quiz_records
        async with db.execute("PRAGMA table_info(quiz_records)") as cursor:
            columns = [c[1] for c in await cursor.fetchall()]
            for col in ["ai_praise", "ai_critique", "improvement_plan"]:
                assert col in columns




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
