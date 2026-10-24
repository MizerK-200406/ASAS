import pytest
from pydantic import ValidationError

from asas.modules.flashcard.schemas import (
    FlashcardItem,
    FlashcardSet,
    FlashcardGenerationRequest,
)


def test_flashcard_schemas_valid():
    """Test valid flashcard item and set creation."""
    card = FlashcardItem(
        front="Overfitting là gì?",
        back="Hiện tượng mô hình học quá kỹ dữ liệu huấn luyện dẫn đến kém tổng quát hóa.",
        hint="Gợi ý: train loss thấp nhưng val loss cao",
        tags=["machine-learning", "deep-learning"],
    )
    assert card.hint is not None
    assert "machine-learning" in card.tags

    fset = FlashcardSet(topic="Machine Learning", cards=[card])
    assert len(fset.cards) == 1
    assert fset.topic == "Machine Learning"


def test_flashcard_generation_request_bounds():
    """Test bounds on FlashcardGenerationRequest."""
    req = FlashcardGenerationRequest(content_or_topic="Transformer architecture", num_cards=10)
    assert req.num_cards == 10

    with pytest.raises(ValidationError):
        FlashcardGenerationRequest(content_or_topic="AI", num_cards=0)
