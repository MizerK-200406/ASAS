"""Unit tests for MemoryService orchestrating session memory and repository."""

import pytest
import pytest_asyncio
from asas.core.config import get_settings
from asas.modules.memory.db import get_db_connection
from asas.modules.memory.service import MemoryService


@pytest_asyncio.fixture(autouse=True)
async def clean_test_db():
    """Tự động dọn dẹp các bảng trong test database trước mỗi test case."""
    settings = get_settings()
    async with get_db_connection(settings.test_database_url) as conn:
        await conn.execute("TRUNCATE TABLE chat_messages, chat_sessions, student_activity_logs, quiz_records, students CASCADE;")


@pytest.fixture
def memory_service():
    """Fixture tạo MemoryService trỏ đến PostgreSQL test database."""
    settings = get_settings()
    return MemoryService(db_url=settings.test_database_url)


@pytest.mark.asyncio
async def test_session_management(memory_service):
    """Kiểm tra quản lý phiên hội thoại ngắn hạn qua MemoryService."""
    sess = memory_service.get_or_create_session(
        session_id="session_test",
        system_prompt="Bạn là gia sư",
        max_messages=5,
    )
    sess.add_message("user", "Xin chào")

    same_sess = memory_service.get_session("session_test")
    assert same_sess is not None
    assert len(same_sess.get_messages()) == 1


@pytest.mark.asyncio
async def test_quiz_and_student_summary(memory_service):
    """Kiểm tra ghi nhận kết quả bài kiểm tra và tổng hợp báo cáo học sinh."""
    await memory_service.initialize()
    await memory_service.get_or_create_student("st_01", "Trần Văn B")

    await memory_service.record_quiz_result(
        student_id="st_01",
        topic="Đại số",
        score_percentage=100.0,
        total_questions=5,
        correct_count=5,
    )

    summary = await memory_service.get_student_summary("st_01")
    assert summary["profile"].name == "Trần Văn B"
    assert summary["quiz_stats"]["total_quizzes"] == 1
    assert summary["quiz_stats"]["average_score"] == 100.0
    assert len(summary["recent_quizzes"]) == 1


@pytest.mark.asyncio
async def test_record_quiz_with_ai_feedback_and_activity_log(memory_service):
    """Kiểm tra ghi nhận Quiz kèm nhận xét AI và tự động lưu Activity Log."""
    await memory_service.initialize()
    await memory_service.get_or_create_student("st_phamd", "Phạm Dương", grade_level="Lớp 12")

    await memory_service.record_quiz_result(
        student_id="st_phamd",
        topic="Lượng giác",
        score_percentage=80.0,
        total_questions=5,
        correct_count=4,
        ai_praise="Rất tốt ở các công thức biến đổi tích thành tổng.",
        ai_critique="Cần chú ý điều kiện của tan(x).",
        improvement_plan="Làm thêm 2 bài tập điều kiện xác định.",
    )

    summary = await memory_service.get_student_summary("st_phamd")
    recent = summary["recent_quizzes"][0]
    assert recent.ai_praise == "Rất tốt ở các công thức biến đổi tích thành tổng."
    assert recent.ai_critique == "Cần chú ý điều kiện của tan(x)."
    assert recent.improvement_plan == "Làm thêm 2 bài tập điều kiện xác định."

    # Kiểm tra activity log tự động được ghi lại
    logs = summary.get("recent_activities", [])
    assert len(logs) >= 1
    assert logs[0].action_type == "QUIZ_COMPLETED"
    assert "Lượng giác" in logs[0].description


@pytest.mark.asyncio
async def test_get_all_students_and_quiz_detail(memory_service):
    """Kiểm tra MemoryService cung cấp danh sách học sinh và chi tiết bài quiz."""
    await memory_service.initialize()
    await memory_service.get_or_create_student("st_user1", "Nguyễn Duy Long", grade_level="Lớp 10")
    await memory_service.get_or_create_student("st_user2", "Nguyễn Duy Long", grade_level="Lớp 12")

    students = await memory_service.get_all_students()
    assert len(students) >= 2

    quiz_id = await memory_service.record_quiz_result(
        student_id="st_user1",
        topic="Cơ bản",
        score_percentage=100.0,
        total_questions=2,
        correct_count=2,
        ai_praise="Rất tốt!",
    )

    detail = await memory_service.get_quiz_record_by_id(quiz_id)
    assert detail is not None
    assert detail.id == quiz_id
    assert detail.ai_praise == "Rất tốt!"


@pytest.mark.asyncio
async def test_persistent_chat_service_and_expanded_activity_stream(memory_service):
    """Kiểm tra MemoryService lưu trữ phiên chat bền vững và mở rộng activity stream lên 10 mục."""
    await memory_service.initialize()
    await memory_service.get_or_create_student("st_user1", "Nguyễn Duy Long")

    # Tạo phiên chat
    session = await memory_service.get_or_create_persistent_session(
        session_id="sess_physics_01",
        student_id="st_user1",
        title="Ôn tập Định luật Newton",
    )
    assert session.id == "sess_physics_01"

    # Lưu tin nhắn
    await memory_service.save_chat_message(
        session_id="sess_physics_01",
        role="user",
        content="Định luật 2 Newton phát biểu thế nào?",
    )
    await memory_service.save_chat_message(
        session_id="sess_physics_01",
        role="assistant",
        content="Gia tốc của một vật tỉ lệ thuận với lực tác dụng: F = m * a.",
        agent_role="tutor",
    )

    messages = await memory_service.get_session_chat_messages("sess_physics_01")
    assert len(messages) == 2
    assert messages[0].content == "Định luật 2 Newton phát biểu thế nào?"
    assert messages[1].agent_role == "tutor"

    # Thêm 10 hoạt động khác nhau
    for i in range(10):
        await memory_service.log_activity(
            student_id="st_user1",
            action_type=f"ACTION_{i}",
            description=f"Mô tả hoạt động số {i}",
        )

    summary = await memory_service.get_student_summary("st_user1")
    assert len(summary["recent_activities"]) == 10


@pytest.mark.asyncio
async def test_memory_service_dual_database_initialization(tmp_path):
    """Kiểm tra MemoryService cấu hình và khởi tạo dual databases (users.db và chats.db)."""
    user_db = str(tmp_path / "custom_users.db")
    chat_db = str(tmp_path / "custom_chats.db")

    service = MemoryService(user_db_path=user_db, chat_db_path=chat_db)
    await service.initialize()

    # Tạo học sinh
    st = await service.get_or_create_student("st_svc_dual", "Le Thi C")
    assert st.name == "Le Thi C"

    # Tạo phiên chat và tin nhắn
    sess = await service.get_or_create_persistent_session(
        session_id="sess_dual_svc_01",
        student_id="st_svc_dual",
        title="Lịch sử Việt Nam",
    )
    assert sess.title == "Lịch sử Việt Nam"

    msg = await service.save_chat_message(
        session_id="sess_dual_svc_01",
        role="user",
        content="Chiến thắng Điện Biên Phủ năm nào?",
    )
    assert msg.id is not None




