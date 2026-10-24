import pytest
from pydantic import ValidationError

from asas.modules.quiz.schemas import (
    DifficultyLevel,
    QuestionType,
    QuizOption,
    QuizQuestion,
    Quiz,
    QuizGenerationRequest,
)


def test_quiz_option_and_question_valid():
    """Test creating a valid multiple-choice quiz question."""
    options = [
        QuizOption(id="A", text="Paris"),
        QuizOption(id="B", text="London"),
        QuizOption(id="C", text="Berlin"),
        QuizOption(id="D", text="Madrid"),
    ]
    q = QuizQuestion(
        question="Thủ đô của nước Pháp là gì?",
        question_type=QuestionType.MULTIPLE_CHOICE,
        options=options,
        correct_answer_id="A",
        explanation="Paris là thủ đô của nước Pháp.",
        difficulty=DifficultyLevel.EASY,
    )
    assert q.correct_answer_id == "A"
    assert len(q.options) == 4


def test_quiz_question_invalid_correct_answer():
    """Test validation fails when correct_answer_id is not in options."""
    options = [
        QuizOption(id="A", text="Option 1"),
        QuizOption(id="B", text="Option 2"),
    ]
    with pytest.raises(ValidationError):
        QuizQuestion(
            question="Câu hỏi mẫu",
            question_type=QuestionType.MULTIPLE_CHOICE,
            options=options,
            correct_answer_id="Z",  # Not in options
            explanation="Giải thích",
            difficulty=DifficultyLevel.MEDIUM,
        )


def test_quiz_generation_request_bounds():
    """Test bounds on num_questions in QuizGenerationRequest."""
    # Valid
    req = QuizGenerationRequest(topic="Python OOP", num_questions=5)
    assert req.num_questions == 5

    # Invalid: less than 1
    with pytest.raises(ValidationError):
        QuizGenerationRequest(topic="Python", num_questions=0)

    # Invalid: more than 20
    with pytest.raises(ValidationError):
        QuizGenerationRequest(topic="Python", num_questions=25)
