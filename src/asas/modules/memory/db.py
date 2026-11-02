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
    name VARCHAR(255) NOT NULL,
    grade_level VARCHAR(50),
    school VARCHAR(255),
    target_subjects JSONB NOT NULL DEFAULT '[]'::jsonb,
    target_goal TEXT,
    learning_style VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

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
    completed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS student_activity_logs (
    id VARCHAR(64) PRIMARY KEY,
    student_id VARCHAR(64) NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
    action_type VARCHAR(100) NOT NULL,
    description TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS chat_sessions (
    id VARCHAR(64) PRIMARY KEY,
    student_id VARCHAR(64) NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(64) NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    agent_role VARCHAR(50),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_quiz_records_student ON quiz_records(student_id);
CREATE INDEX IF NOT EXISTS idx_activity_logs_student ON student_activity_logs(student_id);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_student ON chat_sessions(student_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON chat_messages(session_id);
"""

# Alias schema SQL
SCHEMA_SQL = POSTGRES_SCHEMA_SQL
USER_SCHEMA_SQL = POSTGRES_SCHEMA_SQL
CHAT_SCHEMA_SQL = POSTGRES_SCHEMA_SQL


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


async def init_chat_db(target: Union[asyncpg.Connection, asyncpg.Pool, str]) -> None:
    await init_db(target)


@asynccontextmanager
async def get_db_connection(dsn: Optional[str] = None) -> AsyncGenerator[asyncpg.Connection, None]:
    """Async context manager cung cấp kết nối PostgreSQL từ connection pool."""
    pool = await DatabasePool.get_pool(dsn)
    async with pool.acquire() as conn:
        yield conn
