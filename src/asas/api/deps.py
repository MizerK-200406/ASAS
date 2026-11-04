from fastapi import Request
from asas.core.config import Settings, get_settings
from asas.modules.agents.evaluator import EvaluatorAgent
from asas.modules.agents.generator import QuizGeneratorAgent
from asas.modules.memory.service import MemoryService
from asas.modules.quiz.service import QuizService


def get_app_settings() -> Settings:
    return get_settings()


def get_memory_service(request: Request) -> MemoryService:
    if hasattr(request.app.state, "memory_service") and request.app.state.memory_service is not None:
        return request.app.state.memory_service
    return MemoryService()


def get_generator_agent(request: Request) -> QuizGeneratorAgent:
    if hasattr(request.app.state, "generator_agent") and request.app.state.generator_agent is not None:
        return request.app.state.generator_agent
    return QuizGeneratorAgent()


def get_evaluator_agent(request: Request) -> EvaluatorAgent:
    if hasattr(request.app.state, "evaluator_agent") and request.app.state.evaluator_agent is not None:
        return request.app.state.evaluator_agent
    return EvaluatorAgent()


def get_quiz_service(request: Request) -> QuizService:
    if hasattr(request.app.state, "quiz_service") and request.app.state.quiz_service is not None:
        return request.app.state.quiz_service
    return QuizService(
        generator_agent=get_generator_agent(request),
        evaluator_agent=get_evaluator_agent(request),
    )
