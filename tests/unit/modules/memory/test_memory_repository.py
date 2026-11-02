"""Unit tests for MemoryRepository using PostgreSQL async operations."""

from datetime import datetime, timedelta, timezone
import pytest
import pytest_asyncio
from asas.core.config import get_settings
from asas.modules.memory.db import get_db_connection
from asas.modules.memory.repository import MemoryRepository
from asas.modules.memory.schemas import QuizRecord


@pytest_asyncio.fixture(autouse=True)
async def clean_test_db():
    """Tự động dọn dẹp các bảng trong test database trước mỗi test case."""
    settings = get_settings()
    async with get_db_connection(settings.test_database_url) as conn:
        await conn.execute("TRUNCATE TABLE chat_messages, chat_sessions, student_activity_logs, quiz_records, students CASCADE;")


@pytest.fixture
def repo():
    """Fixture cung cấp MemoryRepository trỏ đến test database."""
    settings = get_settings()
    return MemoryRepository(db_url=settings.test_database_url)


@pytest.mark.asyncio
async def test_get_or_create_student(repo):
    """Kiểm tra tạo mới học sinh và lấy học sinh đã tồn tại."""
    await repo.initialize()
    # Tạo mới
    student1 = await repo.get_or_create_student(
        student_id="student_01",
        name="Nguyen Van A",
        grade_level="12",
        target_subjects=["Toán", "Tin học"],
    )
    assert student1.student_id == "student_01"
    assert student1.name == "Nguyen Van A"
    assert student1.target_subjects == ["Toán", "Tin học"]

    # Gọi lại với cùng ID -> Phải trả về học sinh cũ
    student2 = await repo.get_or_create_student(
        student_id="student_01",
        name="Ten Khac",
    )
    assert student2.student_id == "student_01"
    assert student2.name == "Nguyen Van A"


@pytest.mark.asyncio
async def test_quiz_record_and_statistics(repo):
    """Kiểm tra lưu lịch sử Quiz và tính toán thống kê điểm số."""
    await repo.initialize()
    await repo.get_or_create_student("student_01", "Nguyen Van A")

    # Lưu 2 bài quiz
    q1 = QuizRecord(
        student_id="student_01",
        topic="Python Cơ bản",
        score_percentage=80.0,
        total_questions=5,
        correct_count=4,
    )
    q2 = QuizRecord(
        student_id="student_01",
        topic="Đại số tuyến tính",
        score_percentage=100.0,
        total_questions=5,
        correct_count=5,
    )
    id1 = await repo.save_quiz_record(q1)
    id2 = await repo.save_quiz_record(q2)
    assert id1 > 0
    assert id2 > 0

    # Lấy lịch sử
    history = await repo.get_quiz_history("student_01", limit=10)
    assert len(history) == 2
    # Sắp xếp mới nhất trước
    assert history[0].topic == "Đại số tuyến tính"

    # Thống kê
    stats = await repo.get_quiz_statistics("student_01")
    assert stats["total_quizzes"] == 2
    assert stats["average_score"] == 90.0
    assert stats["highest_score"] == 100.0


@pytest.mark.asyncio
async def test_get_or_create_student_with_extended_fields(repo):
    """Kiểm tra tạo học sinh với các trường mở rộng (school, target_goal, learning_style)."""
    await repo.initialize()
    student = await repo.get_or_create_student(
        student_id="student_ext_01",
        name="Le Thi B",
        grade_level="11",
        school="THPT Chuyên Hà Nội - Amsterdam",
        target_subjects=["Vật lý", "Hóa học"],
        target_goal="Đạt 9+ thi THPT Quốc gia",
        learning_style="Thực hành & Trực quan",
    )
    assert student.school == "THPT Chuyên Hà Nội - Amsterdam"
    assert student.target_goal == "Đạt 9+ thi THPT Quốc gia"
    assert student.learning_style == "Thực hành & Trực quan"
    assert student.updated_at is not None

    # Lấy lại kiểm tra tính bền vững
    retrieved = await repo.get_or_create_student(
        student_id="student_ext_01",
        name="Le Thi B",
    )
    assert retrieved.school == "THPT Chuyên Hà Nội - Amsterdam"
    assert retrieved.target_goal == "Đạt 9+ thi THPT Quốc gia"
    assert retrieved.learning_style == "Thực hành & Trực quan"


@pytest.mark.asyncio
async def test_quiz_record_ai_critique_persistence(repo):
    """Kiểm tra lưu trữ và truy xuất đầy đủ các trường nhận xét AI."""
    await repo.initialize()
    await repo.get_or_create_student("student_quiz_02", "Tran Van C")

    record = QuizRecord(
        student_id="student_quiz_02",
        topic="Hình học không gian",
        score_percentage=75.0,
        total_questions=4,
        correct_count=3,
        ai_praise="Nắm vững định lý ba đường vuông góc.",
        ai_critique="Cần cẩn thận khi tính khoảng cách giữa hai đường chéo nhau.",
        improvement_plan="Làm thêm 5 bài tập về khoảng cách trong tuần này.",
    )
    quiz_id = await repo.save_quiz_record(record)
    assert quiz_id > 0

    history = await repo.get_quiz_history("student_quiz_02", limit=5)
    assert len(history) == 1
    saved = history[0]
    assert saved.ai_praise == "Nắm vững định lý ba đường vuông góc."
    assert saved.ai_critique == "Cần cẩn thận khi tính khoảng cách giữa hai đường chéo nhau."
    assert saved.improvement_plan == "Làm thêm 5 bài tập về khoảng cách trong tuần này."


@pytest.mark.asyncio
async def test_student_activity_logging(repo):
    """Kiểm tra ghi nhận nhật ký hoạt động (StudentActivityLog) đa dạng."""
    await repo.initialize()
    await repo.get_or_create_student("student_act_01", "Hoang Van D")

    # Ghi log làm quiz
    log1 = await repo.log_student_activity(
        student_id="student_act_01",
        action_type="quiz_completed",
        description="Hoàn thành bài kiểm tra Toán 12 với điểm số 85.0%",
    )
    assert log1.id is not None
    assert log1.action_type == "quiz_completed"

    # Lấy danh sách logs
    logs = await repo.get_student_activity_logs("student_act_01", limit=10)
    assert len(logs) == 1
    assert logs[0].action_type == "quiz_completed"


@pytest.mark.asyncio
async def test_get_all_students(repo):
    """Kiểm tra lấy danh sách toàn bộ học sinh có trong CSDL."""
    await repo.initialize()
    await repo.get_or_create_student("s1", "Học sinh 1", grade_level="10")
    await repo.get_or_create_student("s2", "Học sinh 2", grade_level="11")
    await repo.get_or_create_student("s3", "Học sinh 3", grade_level="12")

    all_students = await repo.get_all_students()
    assert len(all_students) == 3
    ids = [s.student_id for s in all_students]
    assert "s1" in ids
    assert "s2" in ids
    assert "s3" in ids


@pytest.mark.asyncio
async def test_get_quiz_record_by_id_drilldown(repo):
    """Kiểm tra truy vấn chi tiết một bài quiz cụ thể theo ID."""
    await repo.initialize()
    await repo.get_or_create_student("st_drill", "Nguyen Drill")

    q = QuizRecord(
        student_id="st_drill",
        topic="Lịch sử",
        score_percentage=90.0,
        total_questions=10,
        correct_count=9,
        ai_praise="Xuất sắc phần lịch sử cận đại",
        ai_critique="Sai sót câu hỏi mốc thời gian 1945",
        improvement_plan="Đọc lại SGK trang 120",
    )
    qid = await repo.save_quiz_record(q)
    fetched = await repo.get_quiz_record_by_id(qid)

    assert fetched is not None
    assert fetched.id == qid
    assert fetched.topic == "Lịch sử"
    assert fetched.score_percentage == 90.0
    assert fetched.ai_praise == "Xuất sắc phần lịch sử cận đại"
    assert fetched.ai_critique == "Sai sót câu hỏi mốc thời gian 1945"
    assert fetched.improvement_plan == "Đọc lại SGK trang 120"


@pytest.mark.asyncio
async def test_chat_session_and_messages_persistence(repo):
    """Kiểm tra lưu trữ và truy xuất chat sessions và messages trong PostgreSQL."""
    await repo.initialize()
    await repo.get_or_create_student("st_chat_01", "Nguyen Van Chat")

    # Tạo phiên chat
    session = await repo.create_or_get_chat_session(
        session_id="sess_01",
        student_id="st_chat_01",
        title="Phiên giải bài Toán Đại số",
    )
    assert session.id == "sess_01"
    assert session.student_id == "st_chat_01"

    # Lưu tin nhắn người dùng và trợ lý
    m1 = await repo.save_chat_message(
        session_id="sess_01",
        role="user",
        content="Cho em hỏi về bất đẳng thức Cauchy",
    )
    assert m1.id > 0
    assert m1.content == "Cho em hỏi về bất đẳng thức Cauchy"

    m2 = await repo.save_chat_message(
        session_id="sess_01",
        role="assistant",
        content="Bất đẳng thức Cauchy phát biểu rằng...",
        agent_role="tutor",
    )
    assert m2.id > m1.id
    assert m2.agent_role == "tutor"

    # Lấy danh sách tin nhắn
    messages = await repo.get_session_chat_messages("sess_01")
    assert len(messages) == 2
    assert messages[0].role == "user"
    assert messages[1].role == "assistant"
    assert messages[1].agent_role == "tutor"


@pytest.mark.asyncio
async def test_dual_database_repository():
    """Kiểm tra MemoryRepository hoạt động chuẩn xác với PostgreSQL."""
    settings = get_settings()
    repo = MemoryRepository(db_url=settings.test_database_url)
    await repo.initialize()

    st = await repo.get_or_create_student("st_dual_01", "Pham Duong", grade_level="Lớp 11")
    assert st.student_id == "st_dual_01"

    sess = await repo.create_or_get_chat_session(
        session_id="sess_dual_01",
        student_id="st_dual_01",
        title="Hỏi bài Sinh học",
    )
    assert sess.student_id == "st_dual_01"
    assert sess.title == "Hỏi bài Sinh học"
