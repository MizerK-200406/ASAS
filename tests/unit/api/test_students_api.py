import pytest
from fastapi.testclient import TestClient
from asas.api.app import create_app
from asas.api.deps import get_memory_service
from asas.modules.memory.service import MemoryService


import asyncio

@pytest.fixture
def memory_service_fixture(tmp_path):
    user_db = str(tmp_path / "test_users.db")
    chat_db = str(tmp_path / "test_chats.db")
    service = MemoryService(user_db_path=user_db, chat_db_path=chat_db)
    asyncio.run(service.initialize())
    return service


@pytest.fixture
def client(memory_service_fixture):
    app = create_app()
    app.dependency_overrides[get_memory_service] = lambda: memory_service_fixture
    return TestClient(app)


def test_create_and_get_students(client):
    # 1. Ban đầu danh sách rỗng
    res = client.get("/api/v1/students")
    assert res.status_code == 200
    assert res.json() == []

    # 2. Tạo hồ sơ học sinh mới
    payload = {
        "student_id": "sv_nguyenvana",
        "name": "Nguyễn Văn A",
        "grade_level": "Lớp 12",
        "school": "THPT Chuyên",
        "target_goals": "Đạt 9+ môn Toán",
    }
    create_res = client.post("/api/v1/students", json=payload)
    assert create_res.status_code == 200
    created = create_res.json()
    assert created["student_id"] == "sv_nguyenvana"
    assert created["name"] == "Nguyễn Văn A"

    # 3. Lấy lại danh sách học sinh
    list_res = client.get("/api/v1/students")
    assert list_res.status_code == 200
    students = list_res.json()
    assert len(students) == 1
    assert students[0]["student_id"] == "sv_nguyenvana"

    # 4. Lấy chi tiết hồ sơ & tóm tắt học sinh
    detail_res = client.get("/api/v1/students/sv_nguyenvana")
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["profile"]["student_id"] == "sv_nguyenvana"
    assert "quiz_stats" in detail
    assert detail["quiz_stats"]["total_quizzes"] == 0

    # 5. Học sinh không tồn tại trả về 404
    not_found_res = client.get("/api/v1/students/non_existent_id")
    assert not_found_res.status_code == 404


def test_student_activities_and_quiz_detail(client):
    # Tạo học sinh
    client.post("/api/v1/students", json={"student_id": "sv_02", "name": "Trần B"})

    # Lấy activities
    act_res = client.get("/api/v1/students/sv_02/activities")
    assert act_res.status_code == 200
    assert isinstance(act_res.json(), list)

    # Lấy quiz record không tồn tại -> 404
    quiz_res = client.get("/api/v1/students/sv_02/quiz-records/9999")
    assert quiz_res.status_code == 404
