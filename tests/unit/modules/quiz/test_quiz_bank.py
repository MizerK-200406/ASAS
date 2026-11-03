from unittest.mock import AsyncMock, MagicMock
import pytest
import pytest_asyncio

from asas.core.config import get_settings
from asas.core.llm_client import LLMClient
from asas.modules.memory.db import get_db_connection
from asas.modules.memory.service import MemoryService
from asas.modules.quiz.schemas import (
    DifficultyLevel,
    QuestionType,
    Quiz,
    QuizGenerationRequest,
    QuizOption,
    QuizQuestion,
)
from asas.modules.quiz.service import QuizService


@pytest_asyncio.fixture(autouse=True)
async def clean_test_db():
    """Dọn dẹp các bảng trong test database trước mỗi test case."""
    settings = get_settings()
    async with get_db_connection(settings.test_database_url) as conn:
        await conn.execute("TRUNCATE TABLE student_answered_questions, questions, quiz_records, students CASCADE;")


@pytest.fixture
def memory_service():
    settings = get_settings()
    return MemoryService(db_url=settings.test_database_url)


@pytest.fixture
def sample_question():
    return QuizQuestion(
        question="Trong Python, hàm nào dùng để kiểm tra kiểu dữ liệu của biến?",
        question_type=QuestionType.MULTIPLE_CHOICE,
        options=[
            QuizOption(id="A", text="type()", misconception=None),
            QuizOption(id="B", text="typeof()", misconception="Nhầm lẫn với cú pháp của JavaScript"),
            QuizOption(id="C", text="isinstance()", misconception="Chỉ dùng so sánh lớp cụ thể, không lấy tên kiểu"),
            QuizOption(id="D", text="check()", misconception="Hàm không tồn tại trong built-in của Python"),
        ],
        correct_answer_id="A",
        explanation="type() là hàm dựng sẵn để lấy kiểu dữ liệu trong Python.",
        difficulty=DifficultyLevel.EASY,
    )


@pytest.mark.asyncio
async def test_question_bank_persistence(memory_service, sample_question):
    """Kiểm tra lưu trữ và truy xuất câu hỏi từ kho CSDL."""
    await memory_service.initialize()

    # 1. Lưu câu hỏi vào kho
    saved_ids = await memory_service.save_questions_to_bank(
        questions=[sample_question],
        topic="Python",
        difficulty="easy",
    )
    assert len(saved_ids) == 1
    assert saved_ids[0] > 0

    # 2. Lấy lại câu hỏi từ kho
    retrieved = await memory_service.get_available_questions_from_bank(
        topic="Python",
        difficulty="easy",
        limit=5,
    )
    assert len(retrieved) == 1
    q = retrieved[0]
    assert q.question == sample_question.question
    assert q.correct_answer_id == "A"
    assert len(q.options) == 4
    # Kiểm tra misconception được lưu trữ chuẩn xác
    opt_b = next(o for o in q.options if o.id == "B")
    assert opt_b.misconception == "Nhầm lẫn với cú pháp của JavaScript"


@pytest.mark.asyncio
async def test_quiz_service_generates_directly(memory_service, sample_question):
    """Kiểm tra QuizService sinh đề trực tiếp từ LLM mà không ghi đè vào DB."""
    await memory_service.initialize()

    sample_quiz = Quiz(
        title="Python Basics",
        topic="Python Basics",
        questions=[sample_question],
        source="ai_generated",
    )

    mock_llm = MagicMock(spec=LLMClient)
    mock_llm.structured_output = AsyncMock(return_value=sample_quiz)

    service = QuizService(llm_client=mock_llm, memory_service=memory_service)

    req = QuizGenerationRequest(
        topic="Python Basics",
        num_questions=1,
        difficulty=DifficultyLevel.EASY,
    )
    quiz = await service.generate_quiz(req)

    assert quiz.source == "ai_generated"
    assert len(quiz.questions) == 1
    mock_llm.structured_output.assert_awaited_once()

    # Xác nhận câu hỏi KHÔNG tự động lưu vào kho CSDL questions
    in_db = await memory_service.get_available_questions_from_bank(
        topic="Python Basics",
        difficulty="easy",
        limit=5,
    )
    assert len(in_db) == 0


def test_grade_quiz_extracts_misconceptions(sample_question):
    """Kiểm tra hàm grade_quiz tự động phát hiện ngộ nhận từ các phương án chọn sai."""
    service = QuizService()
    quiz = Quiz(
        title="Quiz",
        topic="Python",
        questions=[sample_question],
    )

    # Học sinh chọn đáp án B (đáp án sai có gắn misconception)
    result = service.grade_quiz(quiz=quiz, user_answers={0: "B"})

    assert result.correct_count == 0
    assert len(result.misconceptions) == 1
    assert result.misconceptions[0] == "Nhầm lẫn với cú pháp của JavaScript"
    assert result.details[0]["misconception"] == "Nhầm lẫn với cú pháp của JavaScript"
