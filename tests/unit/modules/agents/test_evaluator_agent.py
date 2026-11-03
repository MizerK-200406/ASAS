"""Unit tests for EvaluatorAgent performing critique, grading, and quiz knowledge gap evaluation."""

from unittest.mock import AsyncMock, MagicMock
import pytest

from asas.core.llm_client import LLMClient
from asas.modules.agents.evaluator import EvaluatorAgent
from asas.modules.agents.schemas import AgentRole, EvaluationResult
from asas.modules.quiz.schemas import DifficultyLevel, Quiz, QuizOption, QuizQuestion, QuizGradeResult


@pytest.fixture
def sample_evaluation_result():
    return EvaluationResult(
        score_summary="Đạt 50.0% (1/2 câu)",
        strengths=["Nắm vững khái niệm cơ bản về List"],
        knowledge_gaps=["Nhầm lẫn giữa List và Tuple về tính bất biến (Immutability)"],
        critique="Học sinh chọn phương án cho rằng Tuple có thể sửa đổi được sau khi tạo.",
        recommendations=["Ôn lại tính chất bất biến của Tuple trong Python", "Luyện tập thêm 3 câu hỏi phân biệt"],
        improvement_plan="Xem lại tài liệu Python data structures chương 3.",
    )


@pytest.fixture
def mock_llm_client(sample_evaluation_result):
    client = MagicMock(spec=LLMClient)
    client.structured_output = AsyncMock(return_value=sample_evaluation_result)
    return client


def test_evaluator_agent_initialization(mock_llm_client):
    """Kiểm tra khởi tạo EvaluatorAgent đúng vai trò và system prompt chuẩn phản biện."""
    evaluator = EvaluatorAgent(llm_client=mock_llm_client)
    assert evaluator.role == AgentRole.EVALUATOR
    assert "Evaluator" in evaluator.system_prompt or "Đánh giá" in evaluator.system_prompt


@pytest.mark.asyncio
async def test_evaluator_agent_evaluate_general(mock_llm_client, sample_evaluation_result):
    """Kiểm tra phương thức evaluate_general dùng chung cho đánh giá mở rộng."""
    evaluator = EvaluatorAgent(llm_client=mock_llm_client)
    result = await evaluator.evaluate_general(
        context="Học sinh giải bài toán đệ quy nhưng thiếu base case",
        criteria="Chấm điểm tính đúng đắn thuật toán",
    )
    assert result == sample_evaluation_result
    assert mock_llm_client.structured_output.called


@pytest.mark.asyncio
async def test_evaluator_agent_evaluate_quiz(mock_llm_client, sample_evaluation_result):
    """Kiểm tra EvaluatorAgent chuyên trách đánh giá kết quả làm bài trắc nghiệm."""
    evaluator = EvaluatorAgent(llm_client=mock_llm_client)

    quiz = Quiz(
        title="Python Data Structures Quiz",
        topic="Python",
        questions=[
            QuizQuestion(
                question="List có thể thay đổi không?",
                options=[QuizOption(id="A", text="Có"), QuizOption(id="B", text="Không")],
                correct_answer_id="A",
                explanation="List là mutable",
            ),
            QuizQuestion(
                question="Tuple có thể thay đổi không?",
                options=[QuizOption(id="A", text="Có"), QuizOption(id="B", text="Không")],
                correct_answer_id="B",
                explanation="Tuple là immutable",
            ),
        ],
    )

    grade_result = QuizGradeResult(
        total_questions=2,
        correct_count=1,
        score_percentage=50.0,
        details=[
            {"question_index": 0, "is_correct": True, "user_answer": "A", "correct_answer": "A", "explanation": "List là mutable"},
            {"question_index": 1, "is_correct": False, "user_answer": "A", "correct_answer": "B", "explanation": "Tuple là immutable"},
        ],
    )

    result = await evaluator.evaluate_quiz(
        quiz=quiz,
        user_answers={0: "A", 1: "A"},
        grade_result=grade_result,
        student_name="Nguyen Van A",
    )

    assert result.score_summary == "Đạt 50.0% (1/2 câu)"
    assert len(result.knowledge_gaps) == 1
    assert "Immutability" in result.knowledge_gaps[0]
    assert len(result.strengths) == 1
    assert mock_llm_client.structured_output.called

    # Kiểm tra prompt có chứa thông tin câu đúng/sai và tên học sinh
    call_args = mock_llm_client.structured_output.call_args.kwargs
    messages = call_args["messages"]
    user_prompt = messages[1]["content"]
    assert "Nguyen Van A" in user_prompt
    assert "Python" in user_prompt
    assert "50.0%" in user_prompt
    assert "Tuple là immutable" in user_prompt


@pytest.mark.asyncio
async def test_evaluator_agent_evaluate_quiz_perfect_score(mock_llm_client):
    """Kiểm tra khi học sinh làm đúng 100%, không đưa ra lời khuyên hay lỗ hổng kiến thức và không cần gọi LLM."""
    evaluator = EvaluatorAgent(llm_client=mock_llm_client)

    quiz = Quiz(
        title="Python Basics Quiz",
        topic="Python",
        questions=[
            QuizQuestion(
                question="List có thể thay đổi không?",
                options=[QuizOption(id="A", text="Có"), QuizOption(id="B", text="Không")],
                correct_answer_id="A",
                explanation="List là mutable",
            ),
            QuizQuestion(
                question="Tuple có thể thay đổi không?",
                options=[QuizOption(id="A", text="Có"), QuizOption(id="B", text="Không")],
                correct_answer_id="B",
                explanation="Tuple là immutable",
            ),
        ],
    )

    grade_result = QuizGradeResult(
        total_questions=2,
        correct_count=2,
        score_percentage=100.0,
        details=[
            {"question_index": 0, "is_correct": True, "user_answer": "A", "correct_answer": "A", "explanation": "List là mutable"},
            {"question_index": 1, "is_correct": True, "user_answer": "B", "correct_answer": "B", "explanation": "Tuple là immutable"},
        ],
    )

    result = await evaluator.evaluate_quiz(
        quiz=quiz,
        user_answers={0: "A", 1: "B"},
        grade_result=grade_result,
        student_name="Nguyen Van A",
    )

    # Đảm bảo không có lỗ hổng kiến thức và không có lời khuyên
    assert result.knowledge_gaps == []
    assert result.recommendations == []
    assert result.improvement_plan is None

    # Điểm mạnh và lời khen ngợi vẫn đầy đủ
    assert len(result.strengths) > 0
    assert "xuất sắc" in result.critique
    assert "Nguyen Van A" in result.critique

    # Quan trọng: Không cần tốn token/gọi LLM khi đã đạt 100%
    assert not mock_llm_client.structured_output.called
