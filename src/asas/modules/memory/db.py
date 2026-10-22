"""SQLite database connection and schema initialization using aiosqlite."""

from contextlib import asynccontextmanager
import os
from typing import AsyncGenerator
import aiosqlite

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS students (
    student_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    grade_level TEXT,
    target_subjects TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS quiz_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL,
    topic TEXT NOT NULL,
    score_percentage REAL NOT NULL,
    total_questions INTEGER NOT NULL,
    correct_count INTEGER NOT NULL,
    completed_at TEXT NOT NULL,
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS flashcard_progress (
    card_id TEXT PRIMARY KEY,
    student_id TEXT NOT NULL,
    front TEXT NOT NULL,
    back TEXT NOT NULL,
    repetition INTEGER NOT NULL DEFAULT 0,
    interval_days INTEGER NOT NULL DEFAULT 1,
    ease_factor REAL NOT NULL DEFAULT 2.5,
    next_review TEXT NOT NULL,
    last_reviewed TEXT,
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_quiz_student ON quiz_records(student_id);
CREATE INDEX IF NOT EXISTS idx_flashcard_student_next_review ON flashcard_progress(student_id, next_review);
"""


async def init_db(db: aiosqlite.Connection) -> None:
    """Tạo schema CSDL trên một kết nối SQLite đang mở.

    Args:
        db: Kết nối aiosqlite.Connection.
    """
    await db.executescript(SCHEMA_SQL)
    await db.commit()


@asynccontextmanager
async def get_db_connection(db_path: str = "data/asas.db") -> AsyncGenerator[aiosqlite.Connection, None]:
    """Async context manager cung cấp kết nối CSDL SQLite an toàn và cấu hình chuẩn.

    Args:
        db_path: Đường dẫn file CSDL (hoặc ':memory:' cho in-memory testing).
    """
    if db_path != ":memory:":
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)

    db = await aiosqlite.connect(db_path)
    try:
        await db.execute("PRAGMA foreign_keys = ON;")
        if db_path != ":memory:":
            await db.execute("PRAGMA journal_mode = WAL;")
        yield db
    finally:
        await db.close()
