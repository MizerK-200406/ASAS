from unittest.mock import AsyncMock, MagicMock
import pytest

from asas.core.llm_client import LLMClient, LLMClientError
from asas.modules.flashcard.schemas import (
    FlashcardGenerationRequest,
    FlashcardItem,
    FlashcardSet,
)
from asas.modules.flashcard.service import FlashcardService


@pytest.fixture
def mock_llm_client():
    client = MagicMock(spec=LLMClient)
    client.structured_output = AsyncMock()
    return client


@pytest.fixture
def sample_flashcard_set():
    return FlashcardSet(
        topic="Machine Learning Basics",
        cards=[
            FlashcardItem(
                front="Supervised Learning là gì?",
                back="Phương pháp học máy trong đó mô hình được huấn luyện trên dữ liệu đã có nhãn (input-target pairs).",
                hint="Có dữ liệu nhãn đầu ra",
                tags=["machine-learning", "basics"],
            ),
            FlashcardItem(
                front="Overfitting là gì?",
                back="Hiện tượng mô hình học thuộc lòng dữ liệu train, dẫn đến sai số cao trên tập test/validation.",
                hint="Mất khả năng tổng quát hóa",
                tags=["machine-learning", "diagnostics"],
            ),
        ],
    )


@pytest.mark.asyncio
async def test_generate_flashcards_success(mock_llm_client, sample_flashcard_set):
    """Test generating flashcards successfully calls LLM and returns FlashcardSet."""
    mock_llm_client.structured_output.return_value = sample_flashcard_set
    service = FlashcardService(llm_client=mock_llm_client)

    request = FlashcardGenerationRequest(
        content_or_topic="Machine Learning Basics",
        num_cards=2,
        language="vi",
    )

    result = await service.generate_flashcards(request)

    assert result == sample_flashcard_set
    assert len(result.cards) == 2
    mock_llm_client.structured_output.assert_awaited_once()

    # Verify messages passed to LLM contain the topic
    called_kwargs = mock_llm_client.structured_output.call_args.kwargs
    messages = called_kwargs["messages"]
    assert any("Machine Learning Basics" in msg["content"] for msg in messages)


@pytest.mark.asyncio
async def test_generate_flashcards_handles_llm_error(mock_llm_client):
    """Test generate_flashcards propagates LLMClientError on failure."""
    mock_llm_client.structured_output.side_effect = LLMClientError("API connection timeout")
    service = FlashcardService(llm_client=mock_llm_client)

    request = FlashcardGenerationRequest(
        content_or_topic="Deep Learning",
        num_cards=5,
    )

    with pytest.raises(LLMClientError):
        await service.generate_flashcards(request)


def test_filter_by_tag(sample_flashcard_set):
    """Test filtering flashcards in a set by specific tag (case-insensitive)."""
    service = FlashcardService()

    basics_cards = service.filter_by_tag(sample_flashcard_set, tag="basics")
    assert len(basics_cards) == 1
    assert basics_cards[0].front == "Supervised Learning là gì?"

    ml_cards = service.filter_by_tag(sample_flashcard_set, tag="MACHINE-LEARNING")
    assert len(ml_cards) == 2

    empty_cards = service.filter_by_tag(sample_flashcard_set, tag="nlp")
    assert len(empty_cards) == 0
