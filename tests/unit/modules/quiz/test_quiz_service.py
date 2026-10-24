from unittest.mock import AsyncMock, MagicMock
import pytest

from asas.core.llm_client import LLMClient, LLMClientError
from asas.modules.quiz.schemas import (
    DifficultyLevel,
    QuestionType,
    Quiz,
    QuizGenerationRequest,
    QuizOption,
    QuizQuestion,
)
from asas.modules.quiz.service import QuizService, QuizGradeResult


@pytest.fixture
def mock_llm_client():
    client = MagicMock(spec=LLMClient)
    client.structured_output = AsyncMock()
    return client


@pytest.fixture
def sample_quiz():
    return Quiz(
        title="Kiểm tra Python Cơ bản",
        topic="Python Basics",
        questions=[
            QuizQuestion(
                question="Hàm nào dùng để in ra màn hình trong Python?",
                question_type=QuestionType.MULTIPLE_CHOICE,
                options=[
                    QuizOption(id="A", text="print()"),
                    QuizOption(id="B", text="echo()"),
                    QuizOption(id="C", text="console.log()"),
                    QuizOption(id="D", text="printf()"),
                ],
                correct_answer_id="A",
                explanation="print() là hàm chuẩn trong Python để xuất dữ liệu ra console.",
                difficulty=DifficultyLevel.EASY,
            ),
            QuizQuestion(
                question="Kiểu dữ liệu nào là immutable trong Python?",
                question_type=QuestionType.MULTIPLE_CHOICE,
                options=[
                    QuizOption(id="A", text="list"),
                    QuizOption(id="B", text="dict"),
                    QuizOption(id="C", text="tuple"),
                    QuizOption(id="D", text="set"),
                ],
                correct_answer_id="C",
                explanation="tuple là kiểu dữ liệu bất biến (immutable) trong Python.",
                difficulty=DifficultyLevel.MEDIUM,
            ),
        ],
    )


@pytest.mark.asyncio
async def test_generate_quiz_success(mock_llm_client, sample_quiz):
    """Test generating a quiz calls LLM with structured output and returns Quiz."""
    mock_llm_client.structured_output.return_value = sample_quiz
    service = QuizService(llm_client=mock_llm_client)

    request = QuizGenerationRequest(
        topic="Python Basics",
        num_questions=2,
        difficulty=DifficultyLevel.EASY,
        language="vi",
    )

    result = await service.generate_quiz(request)

    assert result == sample_quiz
    assert len(result.questions) == 2
    mock_llm_client.structured_output.assert_awaited_once()

    # Verify messages passed to LLM contain the topic and difficulty
    called_kwargs = mock_llm_client.structured_output.call_args.kwargs
    messages = called_kwargs["messages"]
    assert any("Python Basics" in msg["content"] for msg in messages)
    assert any("easy" in msg["content"] or "EASY" in msg["content"] for msg in messages)


@pytest.mark.asyncio
async def test_generate_quiz_handles_llm_error(mock_llm_client):
    """Test generate_quiz raises LLMClientError when LLM fails."""
    mock_llm_client.structured_output.side_effect = LLMClientError("API connection timeout")
    service = QuizService(llm_client=mock_llm_client)

    request = QuizGenerationRequest(topic="Docker", num_questions=5)

    with pytest.raises(LLMClientError):
        await service.generate_quiz(request)


def test_grade_quiz_all_correct(sample_quiz):
    """Test grading when student answers all questions correctly."""
    service = QuizService()
    user_answers = {0: "A", 1: "C"}

    result = service.grade_quiz(quiz=sample_quiz, user_answers=user_answers)

    assert isinstance(result, QuizGradeResult)
    assert result.total_questions == 2
    assert result.correct_count == 2
    assert result.score_percentage == 100.0
    assert result.details[0]["is_correct"] is True
    assert result.details[1]["is_correct"] is True


def test_grade_quiz_partial_correct(sample_quiz):
    """Test grading when student answers some questions incorrectly or misses some."""
    service = QuizService()
    user_answers = {0: "A", 1: "B"}  # Question 1 is wrong (B instead of C)

    result = service.grade_quiz(quiz=sample_quiz, user_answers=user_answers)

    assert result.total_questions == 2
    assert result.correct_count == 1
    assert result.score_percentage == 50.0
    assert result.details[0]["is_correct"] is True
    assert result.details[1]["is_correct"] is False
    assert result.details[1]["user_answer"] == "B"
    assert result.details[1]["correct_answer"] == "C"
