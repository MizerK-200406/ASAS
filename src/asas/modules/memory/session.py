"""Session Memory implementation with sliding window buffer for conversational AI."""

import uuid
from typing import Any, Dict, List, Optional, Union
from asas.modules.memory.schemas import ChatMessage, MessageRole


class SessionMemory:
    """Quản lý bộ nhớ ngắn hạn cho một phiên hội thoại với cơ chế Sliding Window."""

    def __init__(
        self,
        session_id: Optional[str] = None,
        system_prompt: Optional[str] = None,
        max_messages: int = 10,
    ) -> None:
        """Khởi tạo SessionMemory.

        Args:
            session_id: Mã định danh phiên học (tự sinh UUID nếu để trống).
            system_prompt: Lời nhắc hệ thống (luôn được giữ lại ở đầu context window).
            max_messages: Số lượng tin nhắn người dùng/trợ lý tối đa được giữ lại trong cửa sổ trượt.
        """
        self.session_id = session_id or str(uuid.uuid4())
        self.system_prompt = system_prompt
        self.max_messages = max_messages
        self._messages: List[ChatMessage] = []

    def add_message(self, role: Union[MessageRole, str], content: str) -> ChatMessage:
        """Thêm một tin nhắn mới vào phiên hội thoại."""
        if isinstance(role, str):
            role = MessageRole(role)
        msg = ChatMessage(role=role, content=content)
        self._messages.append(msg)
        return msg

    def get_messages(self) -> List[ChatMessage]:
        """Lấy toàn bộ lịch sử tin nhắn đã lưu trong phiên."""
        return list(self._messages)

    def to_openai_messages(self) -> List[Dict[str, Any]]:
        """Xuất danh sách tin nhắn sang định dạng chuẩn OpenAI tương thích với LLM API.

        Áp dụng cơ chế Sliding Window: Giữ lại System Prompt (nếu có) và lấy
        `max_messages` tin nhắn gần đây nhất.
        """
        result: List[Dict[str, Any]] = []
        if self.system_prompt:
            result.append({"role": "system", "content": self.system_prompt})

        recent_msgs = (
            self._messages[-self.max_messages :]
            if self.max_messages > 0 and len(self._messages) > self.max_messages
            else self._messages
        )

        for msg in recent_msgs:
            result.append({"role": msg.role.value, "content": msg.content})

        return result

    def clear(self) -> None:
        """Xóa toàn bộ tin nhắn trong phiên (vẫn bảo lưu System Prompt)."""
        self._messages.clear()
