from typing import AsyncGenerator
from fastapi import Request
from asas.core.config import Settings, get_settings
from asas.core.llm_client import LLMClient
from asas.modules.memory.service import MemoryService
from asas.modules.quiz.service import QuizService
from asas.modules.flashcard.service import FlashcardService
from asas.modules.agents.orchestrator import MultiAgentOrchestrator
from asas.modules.tools.registry import create_default_registry


def get_app_settings() -> Settings:
    return get_settings()


def get_memory_service(request: Request) -> MemoryService:
    # Retrieve from app state if initialized, or fallback to default
    if hasattr(request.app.state, "memory_service") and request.app.state.memory_service is not None:
        return request.app.state.memory_service
    return MemoryService(user_db_path="data/users.db", chat_db_path="data/chats.db")


def get_quiz_service(request: Request) -> QuizService:
    if hasattr(request.app.state, "quiz_service") and request.app.state.quiz_service is not None:
        return request.app.state.quiz_service
    return QuizService()


def get_flashcard_service(request: Request) -> FlashcardService:
    if hasattr(request.app.state, "flashcard_service") and request.app.state.flashcard_service is not None:
        return request.app.state.flashcard_service
    return FlashcardService()


def get_orchestrator(request: Request) -> MultiAgentOrchestrator:
    if hasattr(request.app.state, "orchestrator") and request.app.state.orchestrator is not None:
        return request.app.state.orchestrator
    llm_client = LLMClient()
    tool_registry = create_default_registry()
    memory_service = get_memory_service(request)
    return MultiAgentOrchestrator(
        llm_client=llm_client,
        tool_registry=tool_registry,
        memory_service=memory_service,
    )
