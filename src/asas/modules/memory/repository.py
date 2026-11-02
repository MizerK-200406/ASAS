"""Long-term Memory Repository providing async PostgreSQL CRUD for student profile, quiz history, and activity logs."""

from datetime import datetime
import json
from typing import Any, Dict, List, Optional
import uuid

from asas.core.config import get_settings
from asas.modules.memory.db import get_db_connection, init_db
from asas.modules.memory.schemas import (
    ChatMessageRecord,
    ChatSessionRecord,
    QuizRecord,
    StudentActivityLog,
    StudentProfile,
    utc_now,
)


def _to_datetime(val: Any) -> datetime:
    """Chuyển đổi an toàn giá trị datetime từ database (asyncpg hoặc string)."""
    if isinstance(val, datetime):
        return val
    return datetime.fromisoformat(str(val))


class MemoryRepository:
    """Repository quản lý truy xuất và lưu trữ dữ liệu học sinh trong PostgreSQL async."""

    def __init__(
        self,
        db_url: Optional[str] = None,
        db_path: Optional[str] = None,
        user_db_path: Optional[str] = None,
        chat_db_path: Optional[str] = None,
    ) -> None:
        settings = get_settings()
        # Ưu tiên db_url -> test_database_url nếu path có 'test' -> default database_url
        if db_url:
            self.db_url = db_url
        elif (db_path and "test" in str(db_path)) or (user_db_path and "test" in str(user_db_path)):
            self.db_url = settings.test_database_url
        else:
            self.db_url = settings.database_url

    async def initialize(self) -> None:
        """Khởi tạo database schemas trên PostgreSQL."""
        await init_db(self.db_url)

    # -------------------------------------------------------------
    # 1. Student Profile
    # -------------------------------------------------------------

    async def get_or_create_student(
        self,
        student_id: str,
        name: str,
        grade_level: Optional[str] = None,
        school: Optional[str] = None,
        target_subjects: Optional[List[str]] = None,
        target_goal: Optional[str] = None,
        learning_style: Optional[str] = None,
    ) -> StudentProfile:
        """Lấy thông tin học sinh theo ID, hoặc tạo mới nếu chưa tồn tại."""
        async with get_db_connection(self.db_url) as conn:
            row = await conn.fetchrow(
                "SELECT * FROM students WHERE student_id = $1", student_id
            )
            if row:
                raw_subjects = row["target_subjects"]
                parsed_subjects = json.loads(raw_subjects) if isinstance(raw_subjects, str) else list(raw_subjects)
                return StudentProfile(
                    student_id=row["student_id"],
                    name=row["name"],
                    grade_level=row["grade_level"],
                    school=row["school"],
                    target_subjects=parsed_subjects,
                    target_goal=row["target_goal"],
                    learning_style=row["learning_style"],
                    created_at=_to_datetime(row["created_at"]),
                    updated_at=_to_datetime(row["updated_at"]),
                )

            now = utc_now()
            subjects = target_subjects or []
            await conn.execute(
                """
                INSERT INTO students (
                    student_id, name, grade_level, school,
                    target_subjects, target_goal, learning_style,
                    created_at, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """,
                student_id,
                name,
                grade_level,
                school,
                json.dumps(subjects),
                target_goal,
                learning_style,
                now,
                now,
            )
            return StudentProfile(
                student_id=student_id,
                name=name,
                grade_level=grade_level,
                school=school,
                target_subjects=subjects,
                target_goal=target_goal,
                learning_style=learning_style,
                created_at=now,
                updated_at=now,
            )

    async def update_student_profile(self, profile: StudentProfile) -> StudentProfile:
        """Cập nhật thông tin học sinh."""
        now = utc_now()
        async with get_db_connection(self.db_url) as conn:
            await conn.execute(
                """
                UPDATE students
                SET name = $1, grade_level = $2, school = $3,
                    target_subjects = $4, target_goal = $5,
                    learning_style = $6, updated_at = $7
                WHERE student_id = $8
                """,
                profile.name,
                profile.grade_level,
                profile.school,
                json.dumps(profile.target_subjects),
                profile.target_goal,
                profile.learning_style,
                now,
                profile.student_id,
            )
        profile.updated_at = now
        return profile

    async def get_all_students(self) -> List[StudentProfile]:
        """Lấy danh sách tất cả học sinh."""
        async with get_db_connection(self.db_url) as conn:
            rows = await conn.fetch("SELECT * FROM students ORDER BY created_at DESC")
            students = []
            for r in rows:
                raw_sub = r["target_subjects"]
                parsed_sub = json.loads(raw_sub) if isinstance(raw_sub, str) else list(raw_sub)
                students.append(
                    StudentProfile(
                        student_id=r["student_id"],
                        name=r["name"],
                        grade_level=r["grade_level"],
                        school=r["school"],
                        target_subjects=parsed_sub,
                        target_goal=r["target_goal"],
                        learning_style=r["learning_style"],
                        created_at=_to_datetime(r["created_at"]),
                        updated_at=_to_datetime(r["updated_at"]),
                    )
                )
            return students

    # -------------------------------------------------------------
    # 2. Quiz Records & Analytics
    # -------------------------------------------------------------

    async def save_quiz_record(self, record: QuizRecord) -> int:
        """Lưu lịch sử kết quả làm bài trắc nghiệm."""
        async with get_db_connection(self.db_url) as conn:
            quiz_id = await conn.fetchval(
                """
                INSERT INTO quiz_records (
                    student_id, topic, score_percentage,
                    total_questions, correct_count,
                    ai_praise, ai_critique, improvement_plan,
                    completed_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                RETURNING id
                """,
                record.student_id,
                record.topic,
                float(record.score_percentage),
                record.total_questions,
                record.correct_count,
                record.ai_praise,
                record.ai_critique,
                record.improvement_plan,
                record.completed_at,
            )
            return int(quiz_id)

    async def get_quiz_history(self, student_id: str, limit: int = 10) -> List[QuizRecord]:
        """Lấy lịch sử làm bài trắc nghiệm của học sinh gần nhất."""
        async with get_db_connection(self.db_url) as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM quiz_records
                WHERE student_id = $1
                ORDER BY completed_at DESC, id DESC
                LIMIT $2
                """,
                student_id,
                limit,
            )
            return [
                QuizRecord(
                    id=r["id"],
                    student_id=r["student_id"],
                    topic=r["topic"],
                    score_percentage=float(r["score_percentage"]),
                    total_questions=r["total_questions"],
                    correct_count=r["correct_count"],
                    ai_praise=r["ai_praise"],
                    ai_critique=r["ai_critique"],
                    improvement_plan=r["improvement_plan"],
                    completed_at=_to_datetime(r["completed_at"]),
                )
                for r in rows
            ]

    async def get_quiz_record_by_id(self, quiz_id: int) -> Optional[QuizRecord]:
        """Lấy chi tiết một bài quiz theo ID."""
        async with get_db_connection(self.db_url) as conn:
            r = await conn.fetchrow(
                "SELECT * FROM quiz_records WHERE id = $1", quiz_id
            )
            if not r:
                return None
            return QuizRecord(
                id=r["id"],
                student_id=r["student_id"],
                topic=r["topic"],
                score_percentage=float(r["score_percentage"]),
                total_questions=r["total_questions"],
                correct_count=r["correct_count"],
                ai_praise=r["ai_praise"],
                ai_critique=r["ai_critique"],
                improvement_plan=r["improvement_plan"],
                completed_at=_to_datetime(r["completed_at"]),
            )

    async def get_quiz_statistics(self, student_id: str) -> Dict[str, Any]:
        """Tính toán tổng hợp thống kê kết quả học tập từ quiz."""
        async with get_db_connection(self.db_url) as conn:
            row = await conn.fetchrow(
                """
                SELECT 
                    COUNT(*) AS total_quizzes,
                    AVG(score_percentage) AS average_score,
                    MAX(score_percentage) AS highest_score
                FROM quiz_records
                WHERE student_id = $1
                """,
                student_id,
            )
            if not row or row["total_quizzes"] == 0:
                return {
                    "total_quizzes": 0,
                    "average_score": 0.0,
                    "highest_score": 0.0,
                    "recent_quizzes": [],
                }

            recent_records = await self.get_quiz_history(student_id, limit=5)
            return {
                "total_quizzes": int(row["total_quizzes"]),
                "average_score": round(float(row["average_score"]), 2) if row["average_score"] is not None else 0.0,
                "highest_score": round(float(row["highest_score"]), 2) if row["highest_score"] is not None else 0.0,
                "recent_quizzes": recent_records,
            }

    # -------------------------------------------------------------
    # 3. Student Activity Logs
    # -------------------------------------------------------------

    async def log_student_activity(
        self,
        student_id: str,
        action_type: str,
        description: str,
    ) -> StudentActivityLog:
        """Ghi nhận một hoạt động học tập của học sinh."""
        log_id = str(uuid.uuid4())
        now = utc_now()
        async with get_db_connection(self.db_url) as conn:
            await conn.execute(
                """
                INSERT INTO student_activity_logs (id, student_id, action_type, description, created_at)
                VALUES ($1, $2, $3, $4, $5)
                """,
                log_id,
                student_id,
                action_type,
                description,
                now,
            )
        return StudentActivityLog(
            id=log_id,
            student_id=student_id,
            action_type=action_type,
            description=description,
            created_at=now,
        )

    async def get_student_activity_logs(
        self,
        student_id: str,
        limit: int = 20,
    ) -> List[StudentActivityLog]:
        """Lấy danh sách nhật ký hoạt động của học sinh."""
        async with get_db_connection(self.db_url) as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM student_activity_logs
                WHERE student_id = $1
                ORDER BY created_at DESC
                LIMIT $2
                """,
                student_id,
                limit,
            )
            return [
                StudentActivityLog(
                    id=r["id"],
                    student_id=r["student_id"],
                    action_type=r["action_type"],
                    description=r["description"],
                    created_at=_to_datetime(r["created_at"]),
                )
                for r in rows
            ]

    # -------------------------------------------------------------
    # 4. Chat History (Lưu trữ mở rộng)
    # -------------------------------------------------------------

    async def create_or_get_chat_session(
        self,
        session_id: str,
        student_id: str,
        title: Optional[str] = None,
    ) -> ChatSessionRecord:
        """Tạo hoặc lấy phiên hội thoại của học sinh."""
        now = utc_now()
        async with get_db_connection(self.db_url) as conn:
            if session_id:
                row = await conn.fetchrow(
                    "SELECT * FROM chat_sessions WHERE id = $1 AND student_id = $2",
                    session_id,
                    student_id,
                )
                if row:
                    return ChatSessionRecord(
                        id=row["id"],
                        student_id=row["student_id"],
                        title=row["title"],
                        created_at=_to_datetime(row["created_at"]),
                        updated_at=_to_datetime(row["updated_at"]),
                    )

            target_id = session_id or str(uuid.uuid4())
            session_title = title or f"Hội thoại ngày {now.strftime('%d/%m/%Y')}"
            await conn.execute(
                """
                INSERT INTO chat_sessions (id, student_id, title, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5)
                """,
                target_id,
                student_id,
                session_title,
                now,
                now,
            )
            return ChatSessionRecord(
                id=target_id,
                student_id=student_id,
                title=session_title,
                created_at=now,
                updated_at=now,
            )

    async def get_student_chat_sessions(
        self,
        student_id: str,
        limit: int = 10,
    ) -> List[ChatSessionRecord]:
        """Lấy danh sách các phiên chat của học sinh."""
        async with get_db_connection(self.db_url) as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM chat_sessions
                WHERE student_id = $1
                ORDER BY updated_at DESC
                LIMIT $2
                """,
                student_id,
                limit,
            )
            return [
                ChatSessionRecord(
                    id=r["id"],
                    student_id=r["student_id"],
                    title=r["title"],
                    created_at=_to_datetime(r["created_at"]),
                    updated_at=_to_datetime(r["updated_at"]),
                )
                for r in rows
            ]

    async def save_chat_message(
        self,
        session_id: str,
        role: str,
        content: str,
        agent_role: Optional[str] = None,
    ) -> ChatMessageRecord:
        """Lưu một tin nhắn vào phiên hội thoại."""
        now = utc_now()
        async with get_db_connection(self.db_url) as conn:
            msg_id = await conn.fetchval(
                """
                INSERT INTO chat_messages (session_id, role, content, agent_role, created_at)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
                """,
                session_id,
                role,
                content,
                agent_role,
                now,
            )
            await conn.execute(
                "UPDATE chat_sessions SET updated_at = $1 WHERE id = $2",
                now,
                session_id,
            )
            return ChatMessageRecord(
                id=int(msg_id),
                session_id=session_id,
                role=role,
                content=content,
                agent_role=agent_role,
                created_at=now,
            )

    async def get_session_chat_messages(
        self,
        session_id: str,
        limit: int = 50,
    ) -> List[ChatMessageRecord]:
        """Lấy danh sách tin nhắn trong một phiên hội thoại."""
        async with get_db_connection(self.db_url) as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM chat_messages
                WHERE session_id = $1
                ORDER BY id ASC
                LIMIT $2
                """,
                session_id,
                limit,
            )
            return [
                ChatMessageRecord(
                    id=r["id"],
                    session_id=r["session_id"],
                    role=r["role"],
                    content=r["content"],
                    agent_role=r["agent_role"],
                    created_at=_to_datetime(r["created_at"]),
                )
                for r in rows
            ]
