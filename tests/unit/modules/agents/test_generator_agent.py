from unittest.mock import AsyncMock, MagicMock
import pytest

from asas.core.llm_client import LLMClient
from asas.modules.agents.generator import (
    QuizGeneratorAgent,
    sanitize_option_text,
    sanitize_topic,
    shuffle_quiz_options,
)
from asas.modules.agents.schemas import AgentRole
from asas.modules.quiz.schemas import (
    DifficultyLevel,
    QuestionType,
    Quiz,
    QuizGenerationRequest,
    QuizOption,
    QuizQuestion,
)


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
                    QuizOption(id="A", text="print()", misconception=None),
                    QuizOption(id="B", text="echo()", misconception="Nhầm lẫn với cú pháp của PHP/Bash"),
                    QuizOption(id="C", text="console.log()", misconception="Nhầm lẫn với cú pháp của JavaScript"),
                    QuizOption(id="D", text="printf()", misconception="Nhầm lẫn với cú pháp của C/C++"),
                ],
                correct_answer_id="A",
                explanation="Hàm print() là hàm tích hợp sẵn của Python để in ra luồng xuất chuẩn.",
                difficulty=DifficultyLevel.EASY,
            )
        ],
        source="ai_generated",
    )


@pytest.fixture
def mock_llm_client(sample_quiz):
    client = MagicMock(spec=LLMClient)
    client.structured_output = AsyncMock(return_value=sample_quiz)
    return client


def test_generator_agent_initialization(mock_llm_client):
    """Kiểm tra khởi tạo QuizGeneratorAgent đúng vai trò và system prompt chuẩn khảo thí."""
    agent = QuizGeneratorAgent(llm_client=mock_llm_client)
    assert agent.role == AgentRole.GENERATOR
    assert "khảo thí" in agent.system_prompt or "Quiz" in agent.system_prompt


@pytest.mark.asyncio
async def test_generator_agent_generate_success(mock_llm_client, sample_quiz):
    """Kiểm tra QuizGeneratorAgent sinh câu hỏi và tự động làm sạch chủ đề."""
    agent = QuizGeneratorAgent(llm_client=mock_llm_client)

    request = QuizGenerationRequest(
        topic="Toán rời rạc (dễ)",
        num_questions=1,
        difficulty=DifficultyLevel.EASY,
    )

    result = await agent.generate(request)

    assert result.topic == "Toán rời rạc"
    assert result.source == "ai_generated"
    assert len(result.questions) == 1
    mock_llm_client.structured_output.assert_awaited_once()


def test_sanitize_topic():
    """Kiểm tra bóc tách từ khóa độ khó khỏi chủ đề."""
    assert sanitize_topic("Toán rời rạc (khó)") == "Toán rời rạc"
    assert sanitize_topic("Python nâng cao") == "Python"
    assert sanitize_topic("SQL cơ bản") == "SQL"


def test_sanitize_option_text():
    """Kiểm tra làm sạch tiền tố và chữ cái đáp án dính liền."""
    assert sanitize_option_text("A. Normalization", "A") == "Normalization"
    assert sanitize_option_text("ANormalization", "A") == "Normalization"
    assert sanitize_option_text("B) Indexing", "B") == "Indexing"
    assert sanitize_option_text("BDatabase", "B") == "Database"
