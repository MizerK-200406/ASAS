"""Unit tests for PostgreSQL database initialization and schema creation using asyncpg."""

import pytest
import asyncpg
from asas.core.config import get_settings
from asas.modules.memory.db import init_db, get_db_connection


@pytest.fixture
def test_dsn():
    return get_settings().test_database_url


@pytest.mark.asyncio
async def test_init_db_creates_tables(test_dsn):
    """Kiểm tra init_db() tạo thành công các bảng trong PostgreSQL test database."""
    conn = await asyncpg.connect(test_dsn)
    try:
        await init_db(conn)

        # Kiểm tra danh sách bảng trong schema public
        rows = await conn.fetch(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
        )
        tables = [r["table_name"] for r in rows]
        assert "students" in tables
        assert "quiz_records" in tables
        assert "student_activity_logs" in tables
        assert "chat_sessions" not in tables
        assert "chat_messages" not in tables

        # Kiểm tra các cột mở rộng của students
        col_rows = await conn.fetch(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'students'"
        )
        columns = [r["column_name"] for r in col_rows]
        for col in ["school", "target_goal", "learning_style", "updated_at"]:
            assert col in columns

        # Kiểm tra các cột lời phê AI của quiz_records
        q_cols = await conn.fetch(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'quiz_records'"
        )
        columns = [r["column_name"] for r in q_cols]
        for col in ["ai_praise", "ai_critique", "improvement_plan"]:
            assert col in columns
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_foreign_keys_and_schema_constraints(test_dsn):
    """Kiểm tra ràng buộc khóa ngoại (foreign key) hoạt động chính xác trong PostgreSQL."""
    conn = await asyncpg.connect(test_dsn)
    try:
        await init_db(conn)

        # Chèn quiz_record với student_id chưa tồn tại -> Báo lỗi ForeignKeyViolationError
        with pytest.raises(asyncpg.ForeignKeyViolationError):
            await conn.execute(
                """INSERT INTO quiz_records
                   (student_id, topic, score_percentage, total_questions, correct_count, completed_at)
                   VALUES ('non_existent_student', 'Math', 100.0, 5, 5, NOW())"""
            )
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_get_db_connection_context_manager(test_dsn):
    """Kiểm tra async context manager get_db_connection hoạt động với pool."""
    async with get_db_connection(test_dsn) as conn:
        val = await conn.fetchval("SELECT 1")
        assert val == 1
