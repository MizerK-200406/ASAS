"""PostgreSQL database connection, pooling, and schema initialization using asyncpg."""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional, Union
import asyncpg
from loguru import logger

from asas.core.config import get_settings

POSTGRES_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS students (
    student_id VARCHAR(64) PRIMARY KEY,
    device_id VARCHAR(64),
    name VARCHAR(255) NOT NULL,
    grade_level VARCHAR(50),
    school VARCHAR(255),
    target_subjects JSONB NOT NULL DEFAULT '[]'::jsonb,
    target_goal TEXT,
    learning_style VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Migration an toàn cho database đã có sẵn bảng students
ALTER TABLE students ADD COLUMN IF NOT EXISTS device_id VARCHAR(64);
CREATE INDEX IF NOT EXISTS idx_students_device_id ON students(device_id);

CREATE TABLE IF NOT EXISTS quiz_records (
    id SERIAL PRIMARY KEY,
    student_id VARCHAR(64) NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
    topic VARCHAR(255) NOT NULL,
    score_percentage DOUBLE PRECISION NOT NULL,
    total_questions INT NOT NULL,
    correct_count INT NOT NULL,
    ai_praise TEXT,
    ai_critique TEXT,
    improvement_plan TEXT,
    duration_ms DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    prompt_tokens INT NOT NULL DEFAULT 0,
    completion_tokens INT NOT NULL DEFAULT 0,
    total_tokens INT NOT NULL DEFAULT 0,
    completed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Migration an toàn cho database đã có sẵn bảng quiz_records
ALTER TABLE quiz_records ADD COLUMN IF NOT EXISTS duration_ms DOUBLE PRECISION NOT NULL DEFAULT 0.0;
ALTER TABLE quiz_records ADD COLUMN IF NOT EXISTS prompt_tokens INT NOT NULL DEFAULT 0;
ALTER TABLE quiz_records ADD COLUMN IF NOT EXISTS completion_tokens INT NOT NULL DEFAULT 0;
ALTER TABLE quiz_records ADD COLUMN IF NOT EXISTS total_tokens INT NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS questions (
    id SERIAL PRIMARY KEY,
    topic VARCHAR(255) NOT NULL,
    difficulty VARCHAR(50) NOT NULL,
    question TEXT NOT NULL,
    options JSONB NOT NULL,
    correct_answer_id VARCHAR(10) NOT NULL,
    explanation TEXT NOT NULL,
    times_used INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_questions_topic_diff ON questions(topic, difficulty);

CREATE TABLE IF NOT EXISTS student_answered_questions (
    student_id VARCHAR(64) NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
    question_id INT NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    answered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (student_id, question_id)
);

CREATE INDEX IF NOT EXISTS idx_student_answered_questions_student ON student_answered_questions(student_id);

CREATE TABLE IF NOT EXISTS student_activity_logs (
    id VARCHAR(64) PRIMARY KEY,
    student_id VARCHAR(64) NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
    action_type VARCHAR(100) NOT NULL,
    description TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_quiz_records_student ON quiz_records(student_id);
CREATE INDEX IF NOT EXISTS idx_activity_logs_student ON student_activity_logs(student_id);
"""

# Alias schema SQL
SCHEMA_SQL = POSTGRES_SCHEMA_SQL
USER_SCHEMA_SQL = POSTGRES_SCHEMA_SQL


class DatabasePool:
    """Singleton quản lý asyncpg Connection Pool gắn với running event loop."""

    _pools: dict[str, asyncpg.Pool] = {}

    @classmethod
    async def get_pool(cls, dsn: Optional[str] = None) -> asyncpg.Pool:
        target_dsn = dsn or get_settings().database_url
        current_loop = asyncio.get_running_loop()
        existing_pool = cls._pools.get(target_dsn)

        if (
            existing_pool is None
            or existing_pool._closed
            or getattr(existing_pool, "_loop", None) != current_loop
            or existing_pool._loop.is_closed()
        ):
            cls._pools[target_dsn] = await asyncpg.create_pool(
                dsn=target_dsn,
                min_size=1,
                max_size=10,
                command_timeout=60,
            )
        return cls._pools[target_dsn]

    @classmethod
    async def close_all(cls) -> None:
        for dsn, pool in list(cls._pools.items()):
            if not pool._closed:
                await pool.close()
        cls._pools.clear()


async def init_db(target: Union[asyncpg.Connection, asyncpg.Pool, str]) -> None:
    """Tạo schema CSDL trên kết nối hoặc pool PostgreSQL."""
    if isinstance(target, str):
        conn = await asyncpg.connect(target)
        try:
            await conn.execute(POSTGRES_SCHEMA_SQL)
        finally:
            await conn.close()
    elif isinstance(target, asyncpg.Pool):
        async with target.acquire() as conn:
            await conn.execute(POSTGRES_SCHEMA_SQL)
    else:
        await target.execute(POSTGRES_SCHEMA_SQL)


async def init_user_db(target: Union[asyncpg.Connection, asyncpg.Pool, str]) -> None:
    await init_db(target)


@asynccontextmanager
async def get_db_connection(dsn: Optional[str] = None) -> AsyncGenerator[asyncpg.Connection, None]:
    """Async context manager cung cấp kết nối PostgreSQL từ connection pool."""
    pool = await DatabasePool.get_pool(dsn)
    async with pool.acquire() as conn:
        yield conn
