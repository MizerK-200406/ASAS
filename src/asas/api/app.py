from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from asas.core.config import get_settings
from asas.modules.memory.service import MemoryService
from asas.modules.quiz.service import QuizService
from asas.modules.flashcard.service import FlashcardService
from asas.core.llm_client import LLMClient
from asas.modules.tools.registry import create_default_registry
from asas.modules.agents.orchestrator import MultiAgentOrchestrator
from asas.api.v1.router import api_v1_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager to initialize and cleanup resources."""
    logger.info("Khởi động FastAPI server ASAS...")
    
    # Khởi tạo MemoryService
    memory_service = MemoryService(user_db_path="data/users.db", chat_db_path="data/chats.db")
    await memory_service.initialize()
    app.state.memory_service = memory_service

    # Khởi tạo Services khác
    app.state.quiz_service = QuizService()
    app.state.flashcard_service = FlashcardService()

    # Khởi tạo Orchestrator & LLM Client
    llm_client = LLMClient()
    tool_registry = create_default_registry()
    app.state.orchestrator = MultiAgentOrchestrator(
        llm_client=llm_client,
        tool_registry=tool_registry,
        memory_service=memory_service,
    )
    
    logger.info("FastAPI server ASAS đã sẵn sàng!")
    yield
    
    logger.info("Đang tắt FastAPI server ASAS...")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="ASAS - AI Study Assistant API",
        description="Nền tảng Đánh giá & Hỗ trợ Học tập Cá nhân hóa với Kiến trúc Đa tác tử",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include API Routers
    app.include_router(api_v1_router)

    return app


# Application entry point for Uvicorn: uvicorn asas.api.app:app --reload
app = create_app()
