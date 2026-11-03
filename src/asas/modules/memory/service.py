"""MemoryService orchestrating conversational session memory, SQLite persistence, and flashcard management."""

from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid
from loguru import logger

from asas.modules.memory.repository import MemoryRepository
from asas.modules.memory.schemas import (
    QuizRecord,
    StudentActivityLog,
    StudentProfile,
    utc_now,
)
from asas.modules.memory.session import SessionMemory


class MemoryService:
    """Service trung tâm điều phối toàn diện hệ thống bộ nhớ cho AI Study Assistant."""

    def __init__(
        self,
        db_url: Optional[str] = None,
        db_path: Optional[str] = None,
        user_db_path: Optional[str] = None,
        chat_db_path: Optional[str] = None,
    ) -> None:
        self.repository = MemoryRepository(
            db_url=db_url,
            db_path=db_path,
            user_db_path=user_db_path,
            chat_db_path=chat_db_path,
        )
        self._sessions: Dict[str, SessionMemory] = {}

    async def initialize(self) -> None:
        """Khởi tạo database schema nếu chưa tồn tại."""
        await self.repository.initialize()

    # -------------------------------------------------------------
    # 1. Quản lý Session Memory (Bộ nhớ hội thoại ngắn hạn)
    # -------------------------------------------------------------

    def get_or_create_session(
        self,
        session_id: Optional[str] = None,
        system_prompt: Optional[str] = None,
        max_messages: int = 10,
    ) -> SessionMemory:
        """Lấy hoặc tạo mới một phiên hội thoại có quản lý sliding window."""
        sess_id = session_id or str(uuid.uuid4())
        if sess_id not in self._sessions:
            self._sessions[sess_id] = SessionMemory(
                session_id=sess_id,
                system_prompt=system_prompt,
                max_messages=max_messages,
            )
        return self._sessions[sess_id]

    def get_session(self, session_id: str) -> Optional[SessionMemory]:
        """Lấy phiên hội thoại theo session_id."""
        return self._sessions.get(session_id)

    # -------------------------------------------------------------
    # 2. Quản lý Hồ sơ học sinh & Lịch sử học tập
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
        """Lấy hoặc tạo mới hồ sơ học sinh."""
        return await self.repository.get_or_create_student(
            student_id=student_id,
            name=name,
            grade_level=grade_level,
            school=school,
            target_subjects=target_subjects,
            target_goal=target_goal,
            learning_style=learning_style,
        )

    async def get_student_profile(self, student_id: str) -> Optional[StudentProfile]:
        """Lấy thông tin học sinh theo ID."""
        return await self.repository.get_student_profile(student_id)

    async def update_student_profile(self, profile: StudentProfile) -> StudentProfile:
        """Cập nhật thông tin chi tiết hồ sơ học sinh."""
        return await self.repository.update_student_profile(profile)

    async def get_all_students(self) -> List[StudentProfile]:
        """Lấy danh sách tất cả học sinh đã đăng ký trong hệ thống."""
        return await self.repository.get_all_students()

    async def get_quiz_record_by_id(
        self,
        quiz_id: int,
        student_id: Optional[str] = None,
    ) -> Optional[QuizRecord]:
        """Lấy chi tiết một bài quiz theo ID (Master-Detail pattern), có lọc theo student_id nếu được truyền."""
        return await self.repository.get_quiz_record_by_id(quiz_id=quiz_id, student_id=student_id)

    async def get_quiz_record_by_ordinal_or_id(
        self,
        student_id: str,
        identifier: str,
        limit: int = 50,
    ) -> Optional[QuizRecord]:
        """
        Tra cứu bài thi thông minh cho học sinh:
        - Nếu có tiền tố '#' (VD: #1), tra cứu theo ID toàn cục của bài thi.
        - Nếu là số nguyên thông thường (VD: 1, 2):
          + Ưu tiên đối chiếu với Số Thứ Tự (STT 1-based) trong lịch sử bài thi của học sinh.
          + Nếu vượt quá STT, tiếp tục đối chiếu theo ID toàn cục của học sinh đó.
        Đảm bảo không bao giờ truy cập chéo bài thi của học sinh khác.
        """
        raw = identifier.strip()
        is_hash = raw.startswith("#")
        clean_str = raw.lstrip("#")
        if not clean_str.isdigit():
            return None

        val = int(clean_str)
        quizzes = await self.get_quiz_history(student_id=student_id, limit=limit)
        if not quizzes:
            return None

        # 1. Nếu có dấu #, tìm theo ID bài thi
        if is_hash:
            for q in quizzes:
                if q.id == val:
                    return q
            return await self.get_quiz_record_by_id(quiz_id=val, student_id=student_id)

        # 2. Nếu là số thường: ưu tiên STT trong danh sách của học sinh
        if 1 <= val <= len(quizzes):
            return quizzes[val - 1]

        # 3. Dự phòng tìm theo ID nếu số nhập vượt quá phạm vi STT
        for q in quizzes:
            if q.id == val:
                return q

        return await self.get_quiz_record_by_id(quiz_id=val, student_id=student_id)

    async def get_quiz_history(
        self,
        student_id: str,
        limit: int = 10,
    ) -> List[QuizRecord]:
        """Lấy lịch sử làm bài trắc nghiệm của học sinh."""
        return await self.repository.get_quiz_history(
            student_id=student_id,
            limit=limit,
        )


    async def record_quiz_result(
        self,
        student_id: str,
        topic: str,
        score_percentage: float,
        total_questions: int,
        correct_count: int,
        ai_praise: Optional[str] = None,
        ai_critique: Optional[str] = None,
        improvement_plan: Optional[str] = None,
    ) -> int:
        """Ghi nhận kết quả làm bài trắc nghiệm của học sinh kèm nhận xét của AI vào CSDL."""
        record = QuizRecord(
            student_id=student_id,
            topic=topic,
            score_percentage=score_percentage,
            total_questions=total_questions,
            correct_count=correct_count,
            ai_praise=ai_praise,
            ai_critique=ai_critique,
            improvement_plan=improvement_plan,
        )
        row_id = await self.repository.save_quiz_record(record)

        # Tự động ghi nhật ký hoạt động
        desc = f"Làm bài kiểm tra '{topic}': {score_percentage}% ({correct_count}/{total_questions})"
        await self.repository.log_student_activity(
            student_id=student_id,
            action_type="QUIZ_COMPLETED",
            description=desc,
        )
        return row_id

    async def get_student_summary(
        self,
        student_id: str,
        activity_limit: int = 10,
    ) -> Dict[str, Any]:
        """Tổng hợp thông tin hồ sơ, thống kê điểm số, bài kiểm tra và dòng thời gian hoạt động gần nhất."""
        profile = await self.repository.get_or_create_student(
            student_id=student_id,
            name="Học sinh",
        )
        quiz_stats = await self.repository.get_quiz_statistics(student_id)
        recent_quizzes = await self.repository.get_quiz_history(student_id, limit=5)
        recent_activities = await self.repository.get_student_activity_logs(student_id, limit=activity_limit)
        return {
            "profile": profile,
            "quiz_stats": quiz_stats,
            "recent_quizzes": recent_quizzes,
            "recent_activities": recent_activities,
        }


    # -------------------------------------------------------------
    # 4. Quản lý Nhật ký hoạt động (Activity Logs)
    # -------------------------------------------------------------

    async def log_activity(
        self,
        student_id: str,
        action_type: str,
        description: str,
    ) -> StudentActivityLog:
        """Ghi lại vết hoạt động của học sinh."""
        return await self.repository.log_student_activity(
            student_id=student_id,
            action_type=action_type,
            description=description,
        )

    async def get_student_activity_logs(
        self,
        student_id: str,
        limit: int = 10,
    ) -> List[StudentActivityLog]:
        """Lấy danh sách nhật ký hoạt động gần nhất của học sinh."""
        return await self.repository.get_student_activity_logs(
            student_id=student_id,
            limit=limit,
        )
