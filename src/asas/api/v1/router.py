from fastapi import APIRouter
from asas.api.v1.endpoints import health, students, quiz, flashcards, chat

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(health.router)
api_v1_router.include_router(students.router)
api_v1_router.include_router(quiz.router)
api_v1_router.include_router(flashcards.router)
api_v1_router.include_router(chat.router)
