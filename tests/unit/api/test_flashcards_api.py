import pytest
import asyncio
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient

from asas.api.app import create_app
from asas.api.deps import get_memory_service, get_flashcard_service
from asas.modules.memory.service import MemoryService
from asas.modules.flashcard.service import FlashcardService
from asas.modules.flashcard.schemas import (
    FlashcardSet,
    FlashcardItem,
)


@pytest.fixture
def memory_service(tmp_path):
    user_db = str(tmp_path / "test_fc_users.db")
    chat_db = str(tmp_path / "test_fc_chats.db")
    service = MemoryService(user_db_path=user_db, chat_db_path=chat_db)
    asyncio.run(service.initialize())
    return service


@pytest.fixture
def mock_flashcard_service():
    service = FlashcardService()
    sample_set = FlashcardSet(
        topic="Python Cơ bản",
        cards=[
            FlashcardItem(
                front="List trong Python là gì?",
                back="Cấu trúc dữ liệu danh sách có thứ tự và có thể thay đổi (mutable).",
                hint="Dùng ngoặc vuông []",
                tags=["python", "data-structures"],
            ),
            FlashcardItem(
                front="Tuple trong Python khác List thế nào?",
                back="Tuple là bất biến (immutable), không thể thay đổi sau khi tạo.",
                hint="Dùng ngoặc tròn ()",
                tags=["python", "tuples"],
            ),
        ],
    )
    service.generate_flashcards = AsyncMock(return_value=sample_set)
    return service


@pytest.fixture
def client(memory_service, mock_flashcard_service):
    app = create_app()
    app.dependency_overrides[get_memory_service] = lambda: memory_service
    app.dependency_overrides[get_flashcard_service] = lambda: mock_flashcard_service
    return TestClient(app)


def test_generate_flashcards_endpoint(client, mock_flashcard_service):
    response = client.post(
        "/api/v1/flashcards/generate",
        json={
            "content_or_topic": "Python Cơ bản",
            "num_cards": 2,
            "language": "vi",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["topic"] == "Python Cơ bản"
    assert len(data["cards"]) == 2
    assert data["imported_cards"] is None
    mock_flashcard_service.generate_flashcards.assert_called_once()


def test_generate_flashcards_with_auto_import(client, memory_service):
    # Setup student
    asyncio.run(
        memory_service.get_or_create_student(
            student_id="student_fc_01",
            name="Flashcard Learner",
        )
    )

    response = client.post(
        "/api/v1/flashcards/generate",
        json={
            "content_or_topic": "Python Cơ bản",
            "num_cards": 2,
            "language": "vi",
            "student_id": "student_fc_01",
            "auto_import": True,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["topic"] == "Python Cơ bản"
    assert data["imported_cards"] is not None
    assert len(data["imported_cards"]) == 2
    assert data["imported_cards"][0]["student_id"] == "student_fc_01"


def test_get_student_flashcards(client, memory_service):
    # Setup student and import cards directly
    asyncio.run(
        memory_service.get_or_create_student(
            student_id="student_fc_02",
            name="Due Tester",
        )
    )
    card_set = FlashcardSet(
        topic="Lịch sử",
        cards=[
            FlashcardItem(
                front="Chiến thắng Điện Biên Phủ diễn ra năm nào?",
                back="Năm 1954",
                hint="Thế kỷ 20",
                tags=["history"],
            )
        ],
    )
    asyncio.run(memory_service.import_flashcard_set("student_fc_02", card_set))

    # Get student cards
    response = client.get("/api/v1/flashcards/student/student_fc_02")
    assert response.status_code == 200
    cards = response.json()
    assert len(cards) == 1
    assert cards[0]["front"] == "Chiến thắng Điện Biên Phủ diễn ra năm nào?"
    assert cards[0]["student_id"] == "student_fc_02"


def test_import_flashcards_endpoint(client, memory_service):
    asyncio.run(
        memory_service.get_or_create_student(
            student_id="student_fc_import",
            name="Import Tester",
        )
    )
    response = client.post(
        "/api/v1/flashcards/import",
        json={
            "student_id": "student_fc_import",
            "card_set": {
                "topic": "Địa lý",
                "cards": [
                    {
                        "front": "Thủ đô của Việt Nam là gì?",
                        "back": "Hà Nội",
                        "tags": ["geography"],
                    }
                ],
            },
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["front"] == "Thủ đô của Việt Nam là gì?"
    assert data[0]["student_id"] == "student_fc_import"
