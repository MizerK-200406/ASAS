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
        await conn.execute("TRUNCATE TABLE student_activity_logs, quiz_records, students CASCADE;")


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
    assert summary["profile"].student_id == "st_01"
    assert summary["quiz_stats"]["total_quizzes"] == 1
    assert summary["quiz_stats"]["average_score"] == 100.0
    assert len(summary["recent_activities"]) == 1


@pytest.mark.asyncio
async def test_student_profile_extended_fields_in_service(memory_service):
    """Kiểm tra MemoryService khởi tạo và cập nhật học sinh với các trường mở rộng."""
    await memory_service.initialize()
    student = await memory_service.get_or_create_student(
        student_id="st_ext_02",
        name="Vũ Đức Đam",
        grade_level="Đại học",
        school="Đại học Bách Khoa",
        target_subjects=["Trí tuệ nhân tạo", "Hệ điều hành"],
        target_goal="Tốt nghiệp loại xuất sắc",
        learning_style="Thực chiến dự án",
    )
    assert student.school == "Đại học Bách Khoa"
    assert student.target_goal == "Tốt nghiệp loại xuất sắc"
    assert student.learning_style == "Thực chiến dự án"

    # Kiểm tra cập nhật thông tin
    student.school = "Đại học Quốc gia"
    updated = await memory_service.update_student_profile(student)
    assert updated.school == "Đại học Quốc gia"


@pytest.mark.asyncio
async def test_quiz_record_ai_praise_and_critique_via_service(memory_service):
    """Kiểm tra MemoryService lưu trữ và truy xuất đầy đủ nhận xét AI của bài quiz."""
    await memory_service.initialize()
    await memory_service.get_or_create_student("st_quiz_03", "Trần Đình Trọng")

    quiz_id = await memory_service.record_quiz_result(
        student_id="st_quiz_03",
        topic="Vật lý hạt nhân",
        score_percentage=90.0,
        total_questions=10,
        correct_count=9,
        ai_praise="Hiểu rất rõ phản ứng nhiệt hạch.",
        ai_critique="Cần chú ý đơn vị đo chu kỳ bán rã.",
        improvement_plan="Làm lại bài tập 3 và 4 trong SGK.",
    )
    assert quiz_id > 0

    history = await memory_service.get_quiz_history("st_quiz_03", limit=1)
    assert len(history) == 1
    assert history[0].ai_praise == "Hiểu rất rõ phản ứng nhiệt hạch."
    assert history[0].ai_critique == "Cần chú ý đơn vị đo chu kỳ bán rã."
    assert history[0].improvement_plan == "Làm lại bài tập 3 và 4 trong SGK."


@pytest.mark.asyncio
async def test_get_quiz_record_by_id_service(memory_service):
    """Kiểm tra lấy chi tiết một bài quiz cụ thể theo ID."""
    await memory_service.initialize()
    await memory_service.get_or_create_student("st_id_test", "Hoàng Thùy")

    quiz_id = await memory_service.record_quiz_result(
        student_id="st_id_test",
        topic="Hóa vô cơ",
        score_percentage=80.0,
        total_questions=5,
        correct_count=4,
        ai_praise="Rất tốt!",
    )

    detail = await memory_service.get_quiz_record_by_id(quiz_id)
    assert detail is not None
    assert detail.id == quiz_id
    assert detail.ai_praise == "Rất tốt!"


@pytest.mark.asyncio
async def test_expanded_activity_stream(memory_service):
    """Kiểm tra MemoryService mở rộng activity stream lên 10 mục."""
    await memory_service.initialize()
    await memory_service.get_or_create_student("st_user1", "Nguyễn Duy Long")

    # Thêm 10 hoạt động khác nhau
    for i in range(10):
        await memory_service.log_activity(
            student_id="st_user1",
            action_type=f"ACTION_{i}",
            description=f"Mô tả hoạt động số {i}",
        )

    summary = await memory_service.get_student_summary("st_user1")
    assert len(summary["recent_activities"]) == 10
