import uuid
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from asas.api.deps import get_memory_service, get_orchestrator
from asas.modules.agents.orchestrator import MultiAgentOrchestrator
from asas.modules.memory.schemas import (
    ChatMessageRecord,
    ChatSessionRecord,
    utc_now,
)
from asas.modules.memory.service import MemoryService

router = APIRouter(prefix="/chat", tags=["Multi-Agent Chat"])


class ChatMessageRequest(BaseModel):
    """Payload gửi tin nhắn trong phiên hội thoại gia sư AI."""
    student_id: str = Field(..., min_length=1, description="Mã định danh học sinh")
    message: str = Field(..., min_length=1, description="Nội dung câu hỏi hoặc tin nhắn của học sinh")
    session_id: Optional[str] = Field(
        None,
        description="Mã định danh phiên chat (nếu không truyền sẽ tự động tạo mới)",
    )
    title: Optional[str] = Field(
        None,
        description="Tiêu đề phiên hội thoại nếu tạo phiên mới",
    )


class ChatMessageResponse(BaseModel):
    """Phản hồi từ Đa tác tử (Multi-Agent System) sau khi xử lý tin nhắn."""
    session_id: str = Field(..., description="Mã phiên hội thoại")
    role: str = Field(default="assistant", description="Vai trò người phản hồi")
    content: str = Field(..., description="Nội dung câu trả lời sư phạm của Agent")
    agent_role: str = Field(..., description="Agent chuyên trách phụ trách phản hồi (tutor, evaluator, planner)")
    routing_reasoning: Optional[str] = Field(None, description="Lý giải điều phối từ Supervisor Agent")
    created_at: datetime = Field(default_factory=utc_now, description="Thời điểm phản hồi")


@router.post(
    "/message",
    response_model=ChatMessageResponse,
    summary="Gửi tin nhắn chat đến Multi-Agent",
    description="Điều phối tin nhắn học sinh qua Supervisor tới Tutor/Evaluator/Planner và lưu trữ hội thoại bền vững.",
)
async def send_chat_message(
    payload: ChatMessageRequest,
    orchestrator: MultiAgentOrchestrator = Depends(get_orchestrator),
    memory_service: MemoryService = Depends(get_memory_service),
) -> ChatMessageResponse:
    # 1. Khởi tạo hoặc lấy phiên hội thoại
    session_id = payload.session_id or f"sess_{uuid.uuid4().hex[:10]}"
    session_title = payload.title or (
        payload.message[:35] + "..." if len(payload.message) > 35 else payload.message
    )
    await memory_service.get_or_create_persistent_session(
        session_id=session_id,
        student_id=payload.student_id,
        title=session_title,
    )

    # 2. Lưu tin nhắn của học sinh vào CSDL
    await memory_service.save_chat_message(
        session_id=session_id,
        role="user",
        content=payload.message,
    )

    # 3. Lấy lịch sử hội thoại gần nhất để nạp ngữ cảnh cho Multi-Agent
    recent_messages = await memory_service.get_session_chat_messages(
        session_id=session_id,
        limit=20,
    )
    formatted_messages = [
        {"role": msg.role, "content": msg.content}
        for msg in recent_messages
    ]

    # 4. Điều phối thông qua MultiAgentOrchestrator
    decision, agent_response = await orchestrator.dispatch(
        messages=formatted_messages,
        student_id=payload.student_id,
    )

    # 5. Lưu tin nhắn phản hồi của Agent vào CSDL
    await memory_service.save_chat_message(
        session_id=session_id,
        role="assistant",
        content=agent_response.content,
        agent_role=agent_response.agent_role.value,
    )

    return ChatMessageResponse(
        session_id=session_id,
        role="assistant",
        content=agent_response.content,
        agent_role=agent_response.agent_role.value,
        routing_reasoning=decision.reasoning,
        created_at=agent_response.created_at,
    )


@router.get(
    "/sessions/{session_id}",
    response_model=List[ChatMessageRecord],
    summary="Lấy lịch sử tin nhắn của phiên chat",
    description="Trả về danh sách toàn bộ các tin nhắn trong phiên hội thoại theo thứ tự thời gian.",
)
async def get_session_messages(
    session_id: str,
    limit: int = Query(default=50, ge=1, le=200, description="Số lượng tin nhắn tối đa"),
    memory_service: MemoryService = Depends(get_memory_service),
) -> List[ChatMessageRecord]:
    return await memory_service.get_session_chat_messages(
        session_id=session_id,
        limit=limit,
    )


@router.get(
    "/students/{student_id}/sessions",
    response_model=List[ChatSessionRecord],
    summary="Lấy danh sách các phiên chat của học sinh",
    description="Phục vụ hiển thị thanh bên (sidebar) danh sách cuộc trò chuyện học sinh đã tham gia.",
)
async def get_student_sessions(
    student_id: str,
    limit: int = Query(default=30, ge=1, le=100, description="Số lượng phiên tối đa"),
    memory_service: MemoryService = Depends(get_memory_service),
) -> List[ChatSessionRecord]:
    return await memory_service.get_student_chat_sessions(
        student_id=student_id,
        limit=limit,
    )
