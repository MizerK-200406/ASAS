from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from loguru import logger
from starlette.staticfiles import StaticFiles

from asas.api.v1.router import api_v1_router
from asas.core.config import get_settings
from asas.core.llm_client import LLMClient
from asas.modules.agents.evaluator import EvaluatorAgent
from asas.modules.agents.generator import QuizGeneratorAgent
from asas.modules.memory.service import MemoryService
from asas.modules.quiz.service import QuizService


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager to initialize and cleanup resources."""
    logger.info("Khởi động FastAPI server ASAS với PostgreSQL...")

    # Khởi tạo MemoryService kết nối PostgreSQL
    memory_service = MemoryService()
    await memory_service.initialize()
    app.state.memory_service = memory_service

    # Khởi tạo GeneratorAgent, EvaluatorAgent & QuizService (kèm memory_service cho Question Bank)
    llm_client = LLMClient()
    generator_agent = QuizGeneratorAgent(llm_client=llm_client)
    evaluator_agent = EvaluatorAgent(llm_client=llm_client)
    app.state.generator_agent = generator_agent
    app.state.evaluator_agent = evaluator_agent
    app.state.quiz_service = QuizService(
        llm_client=llm_client,
        generator_agent=generator_agent,
        evaluator_agent=evaluator_agent,
        memory_service=memory_service,
    )

    logger.info("FastAPI server ASAS đã sẵn sàng!")
    yield

    logger.info("Đang tắt FastAPI server ASAS và giải phóng connection pool...")
    from asas.modules.memory.db import DatabasePool
    await DatabasePool.close_all()


def create_app() -> FastAPI:
    get_settings()
    app = FastAPI(
        title="ASAS - AI Assessment System",
        description="Nền tảng Đánh giá & Hỗ trợ Học tập Cá nhân hóa với AI Evaluator Agent và Ngân hàng câu hỏi Hybrid",
        version="0.3.0",
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

    # Static files & Web UI
    static_dir = Path(__file__).resolve().parents[3] / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

        @app.get("/", include_in_schema=False)
        async def serve_index() -> FileResponse:
            index_path = static_dir / "index.html"
            return FileResponse(str(index_path))

    return app


# Application entry point for Uvicorn: uvicorn asas.api.app:app --reload
app = create_app()
