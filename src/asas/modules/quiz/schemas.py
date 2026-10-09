from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, model_validator


class DifficultyLevel(str, Enum):
    """Mức độ khó của câu hỏi/chủ đề."""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class QuestionType(str, Enum):
    """Loại câu hỏi kiểm tra."""
    MULTIPLE_CHOICE = "multiple_choice"
    TRUE_FALSE = "true_false"
    SHORT_ANSWER = "short_answer"


class QuizOption(BaseModel):
    """Lựa chọn đáp án cho câu hỏi trắc nghiệm."""
    id: str = Field(..., description="Mã định danh lựa chọn (ví dụ: 'A', 'B', 'C', 'D')")
    text: str = Field(..., description="Nội dung đáp án")


class QuizQuestion(BaseModel):
    """Một câu hỏi trắc nghiệm hoàn chỉnh kèm lời giải thích."""
    question: str = Field(..., description="Nội dung câu hỏi")
    question_type: QuestionType = Field(default=QuestionType.MULTIPLE_CHOICE)
    options: List[QuizOption] = Field(default_factory=list, description="Danh sách lựa chọn (nếu có)")
    correct_answer_id: str = Field(..., description="Mã của đáp án đúng (khớp với option.id)")
    explanation: str = Field(..., description="Giải thích chi tiết vì sao đáp án này đúng")
    difficulty: DifficultyLevel = Field(default=DifficultyLevel.MEDIUM)

    @model_validator(mode="after")
    def validate_correct_answer(self) -> "QuizQuestion":
        """Đảm bảo correct_answer_id tồn tại trong danh sách options nếu câu hỏi có options."""
        if self.options:
            valid_ids = {opt.id for opt in self.options}
            if self.correct_answer_id not in valid_ids:
                raise ValueError(
                    f"correct_answer_id '{self.correct_answer_id}' không nằm trong các options hợp lệ: {valid_ids}"
                )
        return self


class QuizGenerationRequest(BaseModel):
    """Yêu cầu tạo bộ câu hỏi trắc nghiệm."""
    topic: str = Field(..., min_length=2, description="Chủ đề cần tạo câu hỏi")
    num_questions: int = Field(default=5, ge=1, le=20, description="Số lượng câu hỏi cần tạo (1-20)")
    difficulty: DifficultyLevel = Field(default=DifficultyLevel.MEDIUM)
    language: str = Field(default="vi", description="Ngôn ngữ tạo câu hỏi (vi, en, ...)")


class Quiz(BaseModel):
    """Toàn bộ bộ câu hỏi trắc nghiệm."""
    title: str = Field(..., description="Tiêu đề của bài kiểm tra")
    topic: str = Field(..., description="Chủ đề")
    questions: List[QuizQuestion] = Field(..., min_length=1, description="Danh sách các câu hỏi")
