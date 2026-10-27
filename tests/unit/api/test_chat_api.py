import pytest
import asyncio
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient

from asas.api.app import create_app
from asas.api.deps import get_memory_service, get_orchestrator
from asas.modules.agents.orchestrator import MultiAgentOrchestrator
from asas.modules.agents.schemas import AgentResponse, AgentRole, SupervisorDecision
from asas.modules.memory.service import MemoryService


@pytest.fixture
def memory_service(tmp_path):
    user_db = str(tmp_path / "test_chat_users.db")
    chat_db = str(tmp_path / "test_chat_chats.db")
    service = MemoryService(user_db_path=user_db, chat_db_path=chat_db)
    asyncio.run(service.initialize())
    return service


@pytest.fixture
def mock_orchestrator():
    orchestrator = AsyncMock(spec=MultiAgentOrchestrator)
    decision = SupervisorDecision(
        next_agent=AgentRole.TUTOR,
        reasoning="Học sinh hỏi về định lý Toán học nên chuyển cho Tutor.",
        instructions="Giải thích chi tiết và trực quan định lý.",
    )
    agent_response = AgentResponse(
        agent_role=AgentRole.TUTOR,
        content="Định lý Fermat lớn phát biểu rằng không có ba số nguyên dương...",
    )
    orchestrator.dispatch = AsyncMock(return_value=(decision, agent_response))
    return orchestrator


@pytest.fixture
def client(memory_service, mock_orchestrator):
    app = create_app()
    app.dependency_overrides[get_memory_service] = lambda: memory_service
    app.dependency_overrides[get_orchestrator] = lambda: mock_orchestrator
    return TestClient(app)


def test_chat_message_new_session(client, memory_service, mock_orchestrator):
    # Setup student
    asyncio.run(
        memory_service.get_or_create_student(
            student_id="student_chat_01",
            name="Chat Learner",
        )
    )

    response = client.post(
        "/api/v1/chat/message",
        json={
            "student_id": "student_chat_01",
            "message": "Hãy giải thích định lý Fermat cho em",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] is not None
    assert data["role"] == "assistant"
    assert "Fermat" in data["content"]
    assert data["agent_role"] == "tutor"
    assert data["routing_reasoning"] is not None

    mock_orchestrator.dispatch.assert_called_once()

    # Check persistence in DB
    session_id = data["session_id"]
    messages = asyncio.run(memory_service.get_session_chat_messages(session_id))
    assert len(messages) == 2
    assert messages[0].role == "user"
    assert messages[0].content == "Hãy giải thích định lý Fermat cho em"
    assert messages[1].role == "assistant"
    assert messages[1].agent_role == "tutor"


def test_chat_message_existing_session(client, memory_service):
    # Setup student and session
    asyncio.run(
        memory_service.get_or_create_student(
            student_id="student_chat_02",
            name="Session Tester",
        )
    )
    session = asyncio.run(
        memory_service.get_or_create_persistent_session(
            session_id="custom_sess_123",
            student_id="student_chat_02",
            title="Toán cao cấp",
        )
    )

    response = client.post(
        "/api/v1/chat/message",
        json={
            "student_id": "student_chat_02",
            "session_id": "custom_sess_123",
            "message": "Còn định lý Pythagoras thì sao?",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == "custom_sess_123"


def test_get_session_chat_messages(client, memory_service):
    session_id = "history_sess_999"
    asyncio.run(
        memory_service.get_or_create_persistent_session(
            session_id=session_id,
            student_id="student_chat_03",
            title="Lịch sử chat",
        )
    )
    asyncio.run(
        memory_service.save_chat_message(
            session_id=session_id,
            role="user",
            content="Xin chào",
        )
    )
    asyncio.run(
        memory_service.save_chat_message(
            session_id=session_id,
            role="assistant",
            content="Chào bạn! Tôi có thể giúp gì?",
            agent_role="tutor",
        )
    )

    response = client.get(f"/api/v1/chat/sessions/{session_id}")
    assert response.status_code == 200
    messages = response.json()
    assert len(messages) == 2
    assert messages[0]["content"] == "Xin chào"
    assert messages[1]["content"] == "Chào bạn! Tôi có thể giúp gì?"


def test_get_student_chat_sessions(client, memory_service):
    student_id = "student_chat_sidebar"
    asyncio.run(
        memory_service.get_or_create_student(
            student_id=student_id,
            name="Sidebar User",
        )
    )
    asyncio.run(
        memory_service.get_or_create_persistent_session(
            session_id="sidebar_sess_1",
            student_id=student_id,
            title="Bài tập 1",
        )
    )
    asyncio.run(
        memory_service.get_or_create_persistent_session(
            session_id="sidebar_sess_2",
            student_id=student_id,
            title="Bài tập 2",
        )
    )

    response = client.get(f"/api/v1/chat/students/{student_id}/sessions")
    assert response.status_code == 200
    sessions = response.json()
    assert len(sessions) == 2
    session_ids = [s["id"] for s in sessions]
    assert "sidebar_sess_1" in session_ids
    assert "sidebar_sess_2" in session_ids


def test_chat_message_validation_error(client):
    response = client.post(
        "/api/v1/chat/message",
        json={
            "student_id": "student_01",
            "message": "",  # Empty message
        },
    )
    assert response.status_code == 422
