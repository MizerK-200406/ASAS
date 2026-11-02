from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from asas.core.config import get_settings
from asas.core.llm_client import LLMClient
from asas.modules.agents.evaluator import EvaluatorAgent
from asas.modules.memory.service import MemoryService
from asas.modules.quiz.service import QuizService
from asas.api.v1.router import api_v1_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager to initialize and cleanup resources."""
    logger.info("Khởi động FastAPI server ASAS với PostgreSQL...")

    # Khởi tạo MemoryService kết nối PostgreSQL
    memory_service = MemoryService()
    await memory_service.initialize()
    app.state.memory_service = memory_service

    # Khởi tạo EvaluatorAgent & QuizService
    llm_client = LLMClient()
    evaluator_agent = EvaluatorAgent(llm_client=llm_client)
    app.state.evaluator_agent = evaluator_agent
    app.state.quiz_service = QuizService(llm_client=llm_client, evaluator_agent=evaluator_agent)

    logger.info("FastAPI server ASAS đã sẵn sàng!")
    yield

    logger.info("Đang tắt FastAPI server ASAS và giải phóng connection pool...")
    from asas.modules.memory.db import DatabasePool
    await DatabasePool.close_all()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="ASAS - AI Assessment System",
        description="Nền tảng Đánh giá & Hỗ trợ Học tập Cá nhân hóa với AI Evaluator Agent",
        version="0.2.0",
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
