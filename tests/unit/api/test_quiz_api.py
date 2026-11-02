import pytest
import asyncio
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient

from asas.api.app import create_app
from asas.api.deps import get_memory_service, get_quiz_service
from asas.core.config import get_settings
from asas.core.llm_client import LLMParseError
from asas.modules.agents.schemas import EvaluationResult
from asas.modules.memory.db import get_db_connection
from asas.modules.memory.service import MemoryService
from asas.modules.quiz.service import QuizService
from asas.modules.quiz.schemas import (
    Quiz,
    QuizQuestion,
    QuizOption,
    DifficultyLevel,
    QuestionType,
)


@pytest.fixture
def memory_service():
    settings = get_settings()
    service = MemoryService(db_url=settings.test_database_url)

    async def _setup():
        await service.initialize()
        async with get_db_connection(settings.test_database_url) as conn:
            await conn.execute("TRUNCATE TABLE chat_messages, chat_sessions, student_activity_logs, quiz_records, students CASCADE;")

    asyncio.run(_setup())
    return service


@pytest.fixture
def mock_quiz_service():
    service = QuizService()
    sample_quiz = Quiz(
        title="Kiểm tra Toán rời rạc",
        topic="Toán rời rạc",
        questions=[
            QuizQuestion(
                question="Đồ thị liên thông là gì?",
                question_type=QuestionType.MULTIPLE_CHOICE,
                options=[
                    QuizOption(id="A", text="Mọi cặp đỉnh đều có đường đi"),
                    QuizOption(id="B", text="Không có chu trình"),
                ],
                correct_answer_id="A",
                explanation="Theo định nghĩa, đồ thị liên thông có đường đi giữa 2 đỉnh bất kỳ.",
                difficulty=DifficultyLevel.EASY,
            ),
            QuizQuestion(
                question="Cây là đồ thị thế nào?",
                question_type=QuestionType.MULTIPLE_CHOICE,
                options=[
                    QuizOption(id="A", text="Đồ thị có chu trình"),
                    QuizOption(id="B", text="Đồ thị liên thông không có chu trình"),
                ],
                correct_answer_id="B",
                explanation="Cây là đồ thị liên thông và phi chu trình.",
                difficulty=DifficultyLevel.MEDIUM,
            ),
        ],
    )
    service.generate_quiz = AsyncMock(return_value=sample_quiz)
    service.evaluate_quiz_with_agent = AsyncMock(
        return_value=EvaluationResult(
            score_summary="Đạt 50%",
            strengths=["Nắm vững khái niệm về đồ thị liên thông"],
            knowledge_gaps=["Chưa phân biệt được cây và đồ thị có chu trình"],
            critique="Học sinh chọn nhầm định nghĩa của cây.",
            recommendations=["Ôn tập lại cây khung và đồ thị phi chu trình"],
            improvement_plan="Làm bài tập cây nhị phân.",
        )
    )
    return service


@pytest.fixture
def client(memory_service, mock_quiz_service):
    app = create_app()
    app.dependency_overrides[get_memory_service] = lambda: memory_service
    app.dependency_overrides[get_quiz_service] = lambda: mock_quiz_service
    return TestClient(app)


def test_generate_quiz_endpoint(client, mock_quiz_service):
    response = client.post(
        "/api/v1/quiz/generate",
        json={
            "topic": "Toán rời rạc",
            "num_questions": 2,
            "difficulty": "medium",
            "language": "vi",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Kiểm tra Toán rời rạc"
    assert data["topic"] == "Toán rời rạc"
    assert len(data["questions"]) == 2
    mock_quiz_service.generate_quiz.assert_called_once()


def test_generate_quiz_validation_error(client):
    response = client.post(
        "/api/v1/quiz/generate",
        json={
            "topic": "A",  # Min length is 2
            "num_questions": 0,  # Min is 1
        },
    )
    assert response.status_code == 422


def test_generate_quiz_llm_parse_error(client, mock_quiz_service):
    mock_quiz_service.generate_quiz.side_effect = LLMParseError("EOF while parsing a list")
    response = client.post(
        "/api/v1/quiz/generate",
        json={
            "topic": "Git flow",
            "num_questions": 5,
        },
    )
    assert response.status_code == 502
    assert "Mô hình AI phản hồi dữ liệu không chuẩn" in response.json()["detail"]


def test_grade_quiz_anonymous(client, mock_quiz_service):
    quiz_payload = {
        "title": "Kiểm tra Toán",
        "topic": "Toán",
        "questions": [
            {
                "question": "1 + 1 = ?",
                "question_type": "multiple_choice",
                "options": [
                    {"id": "A", "text": "2"},
                    {"id": "B", "text": "3"},
                ],
                "correct_answer_id": "A",
                "explanation": "1 + 1 = 2",
                "difficulty": "easy",
            }
        ],
    }

    response = client.post(
        "/api/v1/quiz/grade",
        json={
            "quiz": quiz_payload,
            "user_answers": {0: "A"},
            "evaluate_with_agent": True,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_questions"] == 1
    assert data["correct_count"] == 1
    assert data["score_percentage"] == 100.0
    assert data["record_id"] is None
    assert len(data["details"]) == 1
    assert data["details"][0]["is_correct"] is True
    assert data["evaluation"] is not None
    assert "cây và đồ thị" in data["evaluation"]["knowledge_gaps"][0]
    mock_quiz_service.evaluate_quiz_with_agent.assert_called_once()


def test_grade_quiz_with_student_record(client, memory_service, mock_quiz_service):
    # Setup student
    asyncio.run(
        memory_service.get_or_create_student(
            student_id="student_quiz_01",
            name="Quiz Taker",
        )
    )

    quiz_payload = {
        "title": "Vật lý hạt nhân",
        "topic": "Vật lý hạt nhân",
        "questions": [
            {
                "question": "Hạt nhân gồm các loại hạt nào?",
                "question_type": "multiple_choice",
                "options": [
                    {"id": "A", "text": "Proton và Electron"},
                    {"id": "B", "text": "Proton và Neutron"},
                ],
                "correct_answer_id": "B",
                "explanation": "Hạt nhân gồm nucleon (proton và neutron).",
                "difficulty": "easy",
            },
            {
                "question": "Lực hạt nhân là gì?",
                "question_type": "multiple_choice",
                "options": [
                    {"id": "A", "text": "Lực hấp dẫn"},
                    {"id": "B", "text": "Lực tương tác mạnh"},
                ],
                "correct_answer_id": "B",
                "explanation": "Lực hạt nhân là lực tương tác mạnh tầm ngắn.",
                "difficulty": "medium",
            },
        ],
    }

    # 1 correct, 1 wrong
    response = client.post(
        "/api/v1/quiz/grade",
        json={
            "student_id": "student_quiz_01",
            "quiz": quiz_payload,
            "user_answers": {0: "B", 1: "A"},
            "evaluate_with_agent": True,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_questions"] == 2
    assert data["correct_count"] == 1
    assert data["score_percentage"] == 50.0
    assert data["record_id"] is not None
    assert data["evaluation"] is not None

    # Check that student profile has updated statistics
    summary = asyncio.run(memory_service.get_student_summary("student_quiz_01"))
    assert summary["quiz_stats"]["total_quizzes"] == 1
    assert summary["quiz_stats"]["average_score"] == 50.0
    assert len(summary["recent_quizzes"]) == 1
    recent_quiz = summary["recent_quizzes"][0]
    assert recent_quiz.ai_praise is not None
    assert recent_quiz.ai_critique is not None
    assert "QUIZ_COMPLETED" in [a.action_type for a in summary["recent_activities"]]
