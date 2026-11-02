"""Long-term Memory Repository providing async SQLite CRUD for student profile, quiz history, and flashcard progress."""

from datetime import datetime
import json
from typing import Any, Dict, List, Optional
import aiosqlite
import uuid
from asas.modules.memory.db import get_db_connection, init_db, init_user_db, init_chat_db
from asas.modules.memory.schemas import (
    ChatMessageRecord,
    ChatSessionRecord,
    QuizRecord,
    StudentActivityLog,
    StudentProfile,
    utc_now,
)


class MemoryRepository:
    """Repository quản lý truy xuất và lưu trữ dữ liệu học sinh trong SQLite async."""

    def __init__(
        self,
        db_path: Optional[str] = None,
        user_db_path: Optional[str] = None,
        chat_db_path: Optional[str] = None,
    ) -> None:
        default_path = db_path or "data/asas.db"
        self.user_db_path = user_db_path or default_path
        self.chat_db_path = chat_db_path or default_path
        self.db_path = self.user_db_path

    async def initialize(self) -> None:
        """Khởi tạo database schemas."""
        if self.user_db_path == self.chat_db_path:
            async with get_db_connection(self.user_db_path) as db:
                await init_db(db)
        else:
            async with get_db_connection(self.user_db_path) as u_db:
                await init_user_db(u_db)
            async with get_db_connection(self.chat_db_path) as c_db:
                await init_chat_db(c_db)

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
        async with get_db_connection(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM students WHERE student_id = ?", (student_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    col_names = row.keys()
                    return StudentProfile(
                        student_id=row["student_id"],
                        name=row["name"],
                        grade_level=row["grade_level"],
                        school=row["school"] if "school" in col_names else None,
                        target_subjects=json.loads(row["target_subjects"]),
                        target_goal=row["target_goal"] if "target_goal" in col_names else None,
                        learning_style=row["learning_style"] if "learning_style" in col_names else None,
                        created_at=datetime.fromisoformat(row["created_at"]),
                        updated_at=(
                            datetime.fromisoformat(row["updated_at"])
                            if "updated_at" in col_names and row["updated_at"]
                            else datetime.fromisoformat(row["created_at"])
                        ),
                    )

            # Tạo mới nếu chưa có
            profile = StudentProfile(
                student_id=student_id,
                name=name,
                grade_level=grade_level,
                school=school,
                target_subjects=target_subjects or [],
                target_goal=target_goal,
                learning_style=learning_style,
            )
            await db.execute(
                """INSERT INTO students (student_id, name, grade_level, school, target_subjects, target_goal, learning_style, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    profile.student_id,
                    profile.name,
                    profile.grade_level,
                    profile.school,
                    json.dumps(profile.target_subjects),
                    profile.target_goal,
                    profile.learning_style,
                    profile.created_at.isoformat(),
                    profile.updated_at.isoformat(),
                ),
            )
            await db.commit()
            return profile

    async def update_student_profile(self, profile: StudentProfile) -> StudentProfile:
        """Cập nhật thông tin học sinh."""
        now = utc_now()
        profile.updated_at = now
        async with get_db_connection(self.db_path) as db:
            await db.execute(
                """UPDATE students
                   SET name = ?, grade_level = ?, school = ?, target_subjects = ?, target_goal = ?, learning_style = ?, updated_at = ?
                   WHERE student_id = ?""",
                (
                    profile.name,
                    profile.grade_level,
                    profile.school,
                    json.dumps(profile.target_subjects),
                    profile.target_goal,
                    profile.learning_style,
                    profile.updated_at.isoformat(),
                    profile.student_id,
                ),
            )
            await db.commit()
            return profile

    async def get_all_students(self) -> List[StudentProfile]:
        """Liệt kê toàn bộ danh sách học sinh hiện có trong cơ sở dữ liệu."""
        async with get_db_connection(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM students ORDER BY updated_at DESC, created_at DESC"
            ) as cursor:
                rows = await cursor.fetchall()
                students: List[StudentProfile] = []
                for row in rows:
                    col_names = row.keys()
                    students.append(
                        StudentProfile(
                            student_id=row["student_id"],
                            name=row["name"],
                            grade_level=row["grade_level"],
                            school=row["school"] if "school" in col_names else None,
                            target_subjects=json.loads(row["target_subjects"]),
                            target_goal=row["target_goal"] if "target_goal" in col_names else None,
                            learning_style=row["learning_style"] if "learning_style" in col_names else None,
                            created_at=datetime.fromisoformat(row["created_at"]),
                            updated_at=(
                                datetime.fromisoformat(row["updated_at"])
                                if "updated_at" in col_names and row["updated_at"]
                                else datetime.fromisoformat(row["created_at"])
                            ),
                        )
                    )
                return students

    # -------------------------------------------------------------
    # 2. Quiz Records & Statistics
    # -------------------------------------------------------------

    async def save_quiz_record(self, record: QuizRecord) -> int:
        """Lưu lại kết quả bài làm Quiz của học sinh kèm nhận xét của AI."""
        async with get_db_connection(self.db_path) as db:
            cursor = await db.execute(
                """INSERT INTO quiz_records
                   (student_id, topic, score_percentage, total_questions, correct_count, ai_praise, ai_critique, improvement_plan, completed_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    record.student_id,
                    record.topic,
                    record.score_percentage,
                    record.total_questions,
                    record.correct_count,
                    record.ai_praise,
                    record.ai_critique,
                    record.improvement_plan,
                    record.completed_at.isoformat(),
                ),
            )
            await db.commit()
            return cursor.lastrowid or 0

    async def get_quiz_history(self, student_id: str, limit: int = 10) -> List[QuizRecord]:
        """Lấy danh sách các bài Quiz gần nhất của học sinh kèm nhận xét của AI."""
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
                col_names = rows[0].keys() if rows else []
                return [
                    QuizRecord(
                        id=row["id"],
                        student_id=row["student_id"],
                        topic=row["topic"],
                        score_percentage=row["score_percentage"],
                        total_questions=row["total_questions"],
                        correct_count=row["correct_count"],
                        ai_praise=row["ai_praise"] if "ai_praise" in col_names else None,
                        ai_critique=row["ai_critique"] if "ai_critique" in col_names else None,
                        improvement_plan=row["improvement_plan"] if "improvement_plan" in col_names else None,
                        completed_at=datetime.fromisoformat(row["completed_at"]),
                    )
                    for row in rows
                ]

    async def get_quiz_record_by_id(self, quiz_id: int) -> Optional[QuizRecord]:
        """Truy xuất chi tiết một bài quiz theo ID (Master-Detail drilldown)."""
        async with get_db_connection(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM quiz_records WHERE id = ?", (quiz_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return None
                col_names = row.keys()
                return QuizRecord(
                    id=row["id"],
                    student_id=row["student_id"],
                    topic=row["topic"],
                    score_percentage=row["score_percentage"],
                    total_questions=row["total_questions"],
                    correct_count=row["correct_count"],
                    ai_praise=row["ai_praise"] if "ai_praise" in col_names else None,
                    ai_critique=row["ai_critique"] if "ai_critique" in col_names else None,
                    improvement_plan=row["improvement_plan"] if "improvement_plan" in col_names else None,
                    completed_at=datetime.fromisoformat(row["completed_at"]),
                )

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
    # 4. Student Activity Logs
    # -------------------------------------------------------------

    async def log_student_activity(
        self,
        student_id: str,
        action_type: str,
        description: str,
        activity_id: Optional[str] = None,
    ) -> StudentActivityLog:
        """Ghi lại vết hoạt động của học sinh vào cơ sở dữ liệu."""
        act_id = activity_id or f"act_{uuid.uuid4().hex[:10]}"
        now = utc_now()
        log_entry = StudentActivityLog(
            id=act_id,
            student_id=student_id,
            action_type=action_type,
            description=description,
            created_at=now,
        )
        async with get_db_connection(self.db_path) as db:
            await db.execute(
                """INSERT INTO student_activity_logs (id, student_id, action_type, description, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    log_entry.id,
                    log_entry.student_id,
                    log_entry.action_type,
                    log_entry.description,
                    log_entry.created_at.isoformat(),
                ),
            )
            await db.commit()
            return log_entry

    async def get_student_activity_logs(
        self,
        student_id: str,
        limit: int = 10,
    ) -> List[StudentActivityLog]:
        """Truy xuất danh sách các hành động gần nhất của học sinh."""
        async with get_db_connection(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """SELECT * FROM student_activity_logs
                   WHERE student_id = ?
                   ORDER BY created_at DESC, id DESC
                   LIMIT ?""",
                (student_id, limit),
            ) as cursor:
                rows = await cursor.fetchall()
                return [
                    StudentActivityLog(
                        id=row["id"],
                        student_id=row["student_id"],
                        action_type=row["action_type"],
                        description=row["description"],
                        created_at=datetime.fromisoformat(row["created_at"]),
                    )
                    for row in rows
                ]

    # -------------------------------------------------------------
    # 5. Persistent Chat Sessions & Messages (Lưu hội thoại bền vững)
    # -------------------------------------------------------------

    async def create_or_get_chat_session(
        self,
        session_id: str,
        student_id: str,
        title: str = "Hội thoại học tập",
    ) -> ChatSessionRecord:
        """Lấy phiên hội thoại hiện có hoặc tạo mới nếu chưa tồn tại."""
        async with get_db_connection(self.chat_db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM chat_sessions WHERE id = ?", (session_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return ChatSessionRecord(
                        id=row["id"],
                        student_id=row["student_id"],
                        title=row["title"],
                        created_at=datetime.fromisoformat(row["created_at"]),
                        updated_at=datetime.fromisoformat(row["updated_at"]),
                    )

            now = utc_now()
            session = ChatSessionRecord(
                id=session_id,
                student_id=student_id,
                title=title,
                created_at=now,
                updated_at=now,
            )
            await db.execute(
                """INSERT INTO chat_sessions (id, student_id, title, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    session.id,
                    session.student_id,
                    session.title,
                    session.created_at.isoformat(),
                    session.updated_at.isoformat(),
                ),
            )
            await db.commit()
            return session

    async def get_student_chat_sessions(
        self,
        student_id: str,
        limit: int = 20,
    ) -> List[ChatSessionRecord]:
        """Lấy danh sách các phiên chat của học sinh (phục vụ sidebar trên Web)."""
        async with get_db_connection(self.chat_db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """SELECT * FROM chat_sessions
                   WHERE student_id = ?
                   ORDER BY updated_at DESC, created_at DESC
                   LIMIT ?""",
                (student_id, limit),
            ) as cursor:
                rows = await cursor.fetchall()
                return [
                    ChatSessionRecord(
                        id=row["id"],
                        student_id=row["student_id"],
                        title=row["title"],
                        created_at=datetime.fromisoformat(row["created_at"]),
                        updated_at=datetime.fromisoformat(row["updated_at"]),
                    )
                    for row in rows
                ]

    async def save_chat_message(
        self,
        session_id: str,
        role: str,
        content: str,
        agent_role: Optional[str] = None,
    ) -> ChatMessageRecord:
        """Lưu bền vững một tin nhắn trong phiên chat vào CSDL SQLite."""
        now = utc_now()
        async with get_db_connection(self.chat_db_path) as db:
            cursor = await db.execute(
                """INSERT INTO chat_messages (session_id, role, content, agent_role, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (session_id, role, content, agent_role, now.isoformat()),
            )
            message_id = cursor.lastrowid

            # Cập nhật updated_at của session
            await db.execute(
                "UPDATE chat_sessions SET updated_at = ? WHERE id = ?",
                (now.isoformat(), session_id),
            )
            await db.commit()

            return ChatMessageRecord(
                id=message_id,
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
        """Truy xuất toàn bộ lịch sử tin nhắn của một phiên chat theo thứ tự thời gian."""
        async with get_db_connection(self.chat_db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """SELECT * FROM chat_messages
                   WHERE session_id = ?
                   ORDER BY id ASC
                   LIMIT ?""",
                (session_id, limit),
            ) as cursor:
                rows = await cursor.fetchall()
                return [
                    ChatMessageRecord(
                        id=row["id"],
                        session_id=row["session_id"],
                        role=row["role"],
                        content=row["content"],
                        agent_role=row["agent_role"],
                        created_at=datetime.fromisoformat(row["created_at"]),
                    )
                    for row in rows
                ]


