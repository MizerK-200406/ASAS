"""Long-term Memory Repository providing async PostgreSQL CRUD for student profile, quiz history, activity logs, and question bank."""

from datetime import datetime
import json
from typing import Any, Dict, List, Optional
import uuid

from asas.core.config import get_settings
from asas.modules.memory.db import get_db_connection, init_db
from asas.modules.memory.schemas import (
    QuizRecord,
    StudentActivityLog,
    StudentProfile,
    utc_now,
)
from asas.modules.quiz.schemas import DifficultyLevel, QuizOption, QuizQuestion


def _to_datetime(val: Any) -> datetime:
    """Chuyển đổi an toàn giá trị datetime từ database (asyncpg hoặc string)."""
    if isinstance(val, datetime):
        return val
    return datetime.fromisoformat(str(val))


class MemoryRepository:
    """Repository quản lý truy xuất và lưu trữ dữ liệu học sinh và ngân hàng câu hỏi trong PostgreSQL async."""

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
        device_id: Optional[str] = None,
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
                    device_id=row.get("device_id"),
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
                    student_id, device_id, name, grade_level, school,
                    target_subjects, target_goal, learning_style,
                    created_at, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                """,
                student_id,
                device_id,
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
                device_id=device_id,
                grade_level=grade_level,
                school=school,
                target_subjects=subjects,
                target_goal=target_goal,
                learning_style=learning_style,
                created_at=now,
                updated_at=now,
            )

    async def get_student_profile(self, student_id: str) -> Optional[StudentProfile]:
        """Lấy thông tin học sinh theo ID, trả về None nếu không tồn tại."""
        async with get_db_connection(self.db_url) as conn:
            row = await conn.fetchrow(
                "SELECT * FROM students WHERE student_id = $1", student_id
            )
            if not row:
                return None
            raw_subjects = row["target_subjects"]
            parsed_subjects = json.loads(raw_subjects) if isinstance(raw_subjects, str) else list(raw_subjects)
            return StudentProfile(
                student_id=row["student_id"],
                name=row["name"],
                device_id=row.get("device_id"),
                grade_level=row["grade_level"],
                school=row["school"],
                target_subjects=parsed_subjects,
                target_goal=row["target_goal"],
                learning_style=row["learning_style"],
                created_at=_to_datetime(row["created_at"]),
                updated_at=_to_datetime(row["updated_at"]),
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

    async def get_all_students(self, device_id: Optional[str] = None) -> List[StudentProfile]:
        """Lấy danh sách học sinh (có thể lọc theo device_id để cách ly thiết bị)."""
        async with get_db_connection(self.db_url) as conn:
            if device_id:
                rows = await conn.fetch(
                    "SELECT * FROM students WHERE device_id = $1 ORDER BY created_at DESC",
                    device_id,
                )
            else:
                rows = await conn.fetch("SELECT * FROM students ORDER BY created_at DESC")
            students = []
            for r in rows:
                raw_sub = r["target_subjects"]
                parsed_sub = json.loads(raw_sub) if isinstance(raw_sub, str) else list(raw_sub)
                students.append(
                    StudentProfile(
                        student_id=r["student_id"],
                        name=r["name"],
                        device_id=r.get("device_id"),
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
        """Lưu lịch sử kết quả làm bài trắc nghiệm kèm telemetry."""
        async with get_db_connection(self.db_url) as conn:
            quiz_id = await conn.fetchval(
                """
                INSERT INTO quiz_records (
                    student_id, topic, score_percentage,
                    total_questions, correct_count,
                    ai_praise, ai_critique, improvement_plan,
                    duration_ms, prompt_tokens, completion_tokens, total_tokens,
                    completed_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
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
                float(record.duration_ms),
                int(record.prompt_tokens),
                int(record.completion_tokens),
                int(record.total_tokens),
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
                    duration_ms=float(r["duration_ms"]) if "duration_ms" in r and r["duration_ms"] is not None else 0.0,
                    prompt_tokens=int(r["prompt_tokens"]) if "prompt_tokens" in r and r["prompt_tokens"] is not None else 0,
                    completion_tokens=int(r["completion_tokens"]) if "completion_tokens" in r and r["completion_tokens"] is not None else 0,
                    total_tokens=int(r["total_tokens"]) if "total_tokens" in r and r["total_tokens"] is not None else 0,
                    completed_at=_to_datetime(r["completed_at"]),
                )
                for r in rows
            ]

    async def get_quiz_record_by_id(
        self,
        quiz_id: int,
        student_id: Optional[str] = None,
    ) -> Optional[QuizRecord]:
        """Lấy chi tiết một bài quiz theo ID (có lọc theo student_id để bảo vệ quyền riêng tư)."""
        async with get_db_connection(self.db_url) as conn:
            if student_id:
                r = await conn.fetchrow(
                    "SELECT * FROM quiz_records WHERE id = $1 AND student_id = $2",
                    quiz_id,
                    student_id,
                )
            else:
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
                duration_ms=float(r["duration_ms"]) if "duration_ms" in r and r["duration_ms"] is not None else 0.0,
                prompt_tokens=int(r["prompt_tokens"]) if "prompt_tokens" in r and r["prompt_tokens"] is not None else 0,
                completion_tokens=int(r["completion_tokens"]) if "completion_tokens" in r and r["completion_tokens"] is not None else 0,
                total_tokens=int(r["total_tokens"]) if "total_tokens" in r and r["total_tokens"] is not None else 0,
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
                    MAX(score_percentage) AS highest_score,
                    COALESCE(SUM(correct_count), 0) AS total_correct,
                    COALESCE(SUM(total_questions), 0) AS total_questions
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
                    "total_correct": 0,
                    "total_questions": 0,
                    "recent_quizzes": [],
                }

            recent_records = await self.get_quiz_history(student_id, limit=5)
            return {
                "total_quizzes": int(row["total_quizzes"]),
                "average_score": round(float(row["average_score"]), 2) if row["average_score"] is not None else 0.0,
                "highest_score": round(float(row["highest_score"]), 2) if row["highest_score"] is not None else 0.0,
                "total_correct": int(row["total_correct"]),
                "total_questions": int(row["total_questions"]),
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
    # 4. Question Bank (Kho lưu trữ câu hỏi & Ngộ nhận)
    # -------------------------------------------------------------

    async def save_questions(
        self,
        questions: List[QuizQuestion],
        topic: str,
        difficulty: str,
    ) -> List[int]:
        """Lưu danh sách câu hỏi trắc nghiệm vào kho câu hỏi trong CSDL."""
        saved_ids: List[int] = []
        cleaned_topic = topic.strip().lower()
        cleaned_diff = difficulty.strip().lower()

        async with get_db_connection(self.db_url) as conn:
            for q in questions:
                options_data = [opt.model_dump() for opt in q.options]
                qid = await conn.fetchval(
                    """
                    INSERT INTO questions (
                        topic, difficulty, question, options,
                        correct_answer_id, explanation, times_used, created_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
                    RETURNING id
                    """,
                    cleaned_topic,
                    cleaned_diff,
                    q.question.strip(),
                    json.dumps(options_data, ensure_ascii=False),
                    q.correct_answer_id,
                    q.explanation,
                    1,
                )
                q.id = int(qid)
                saved_ids.append(int(qid))
        return saved_ids

    async def get_available_questions(
        self,
        topic: str,
        difficulty: str,
        limit: int,
        student_id: Optional[str] = None,
    ) -> List[QuizQuestion]:
        """
        Lấy danh sách câu hỏi từ kho:
        - Khớp topic và độ khó.
        - Trừ đi các câu hỏi mà student_id này đã từng làm.
        - Ưu tiên câu hỏi ít dùng và xáo trộn ngẫu nhiên.
        """
        cleaned_topic = topic.strip().lower()
        cleaned_diff = difficulty.strip().lower()

        async with get_db_connection(self.db_url) as conn:
            if student_id:
                query = """
                SELECT * FROM questions
                WHERE LOWER(topic) = $1 AND LOWER(difficulty) = $2
                  AND id NOT IN (
                      SELECT question_id FROM student_answered_questions
                      WHERE student_id = $3
                  )
                ORDER BY times_used ASC, RANDOM()
                LIMIT $4
                """
                rows = await conn.fetch(query, cleaned_topic, cleaned_diff, student_id, limit)
            else:
                query = """
                SELECT * FROM questions
                WHERE LOWER(topic) = $1 AND LOWER(difficulty) = $2
                ORDER BY times_used ASC, RANDOM()
                LIMIT $3
                """
                rows = await conn.fetch(query, cleaned_topic, cleaned_diff, limit)

            result: List[QuizQuestion] = []
            for r in rows:
                opts_raw = r["options"]
                opts_list = json.loads(opts_raw) if isinstance(opts_raw, str) else list(opts_raw)
                options = [QuizOption(**opt) for opt in opts_list]
                diff_enum = DifficultyLevel(r["difficulty"]) if r["difficulty"] in [d.value for d in DifficultyLevel] else DifficultyLevel.MEDIUM
                result.append(
                    QuizQuestion(
                        id=r["id"],
                        question=r["question"],
                        options=options,
                        correct_answer_id=r["correct_answer_id"],
                        explanation=r["explanation"],
                        difficulty=diff_enum,
                    )
                )

            # Cập nhật times_used
            if result:
                q_ids = [q.id for q in result if q.id is not None]
                if q_ids:
                    await conn.execute(
                        "UPDATE questions SET times_used = times_used + 1 WHERE id = ANY($1::int[])",
                        q_ids,
                    )

            return result

    async def mark_questions_answered(self, student_id: str, question_ids: List[int]) -> None:
        """Đánh dấu học sinh đã hoàn thành các câu hỏi để tránh lặp lại."""
        if not student_id or not question_ids:
            return

        async with get_db_connection(self.db_url) as conn:
            for qid in question_ids:
                await conn.execute(
                    """
                    INSERT INTO student_answered_questions (student_id, question_id, answered_at)
                    VALUES ($1, $2, NOW())
                    ON CONFLICT (student_id, question_id) DO NOTHING
                    """,
                    student_id,
                    qid,
                )
