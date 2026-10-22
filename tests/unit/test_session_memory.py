"""Unit tests for SessionMemory (Sliding Window Buffer)."""

from asas.modules.memory.schemas import MessageRole
from asas.modules.memory.session import SessionMemory


def test_session_memory_add_and_get():
    """Kiểm tra thêm tin nhắn và lấy danh sách tin nhắn."""
    mem = SessionMemory(session_id="sess_123")
    assert mem.session_id == "sess_123"
    assert len(mem.get_messages()) == 0

    mem.add_message(role=MessageRole.USER, content="Chào bạn")
    mem.add_message(role=MessageRole.ASSISTANT, content="Chào học sinh!")

    msgs = mem.get_messages()
    assert len(msgs) == 2
    assert msgs[0].role == MessageRole.USER
    assert msgs[0].content == "Chào bạn"
    assert msgs[1].role == MessageRole.ASSISTANT
    assert msgs[1].content == "Chào học sinh!"


def test_session_memory_to_openai_messages():
    """Kiểm tra xuất danh sách tin nhắn sang định dạng chuẩn OpenAI."""
    mem = SessionMemory(system_prompt="Bạn là gia sư AI")
    mem.add_message(role=MessageRole.USER, content="Giải thích về hàm print()")

    openai_msgs = mem.to_openai_messages()
    assert len(openai_msgs) == 2
    assert openai_msgs[0] == {"role": "system", "content": "Bạn là gia sư AI"}
    assert openai_msgs[1] == {"role": "user", "content": "Giải thích về hàm print()"}


def test_session_memory_sliding_window_preserves_system_prompt():
    """Kiểm tra cơ chế Sliding Window cắt tỉa tin nhắn cũ nhưng LUÔN giữ lại System Prompt."""
    # max_messages=4 (tối đa 4 tin nhắn người dùng/trợ lý gần nhất)
    mem = SessionMemory(max_messages=4, system_prompt="Hệ thống gia sư Toán")

    mem.add_message(MessageRole.USER, "Câu hỏi 1")
    mem.add_message(MessageRole.ASSISTANT, "Trả lời 1")
    mem.add_message(MessageRole.USER, "Câu hỏi 2")
    mem.add_message(MessageRole.ASSISTANT, "Trả lời 2")
    mem.add_message(MessageRole.USER, "Câu hỏi 3")
    mem.add_message(MessageRole.ASSISTANT, "Trả lời 3")

    openai_msgs = mem.to_openai_messages()
    # Phải có: 1 tin nhắn System + 4 tin nhắn gần nhất (Câu hỏi 2, Trả lời 2, Câu hỏi 3, Trả lời 3)
    assert len(openai_msgs) == 5
    assert openai_msgs[0]["role"] == "system"
    assert openai_msgs[0]["content"] == "Hệ thống gia sư Toán"

    assert openai_msgs[1]["content"] == "Câu hỏi 2"
    assert openai_msgs[2]["content"] == "Trả lời 2"
    assert openai_msgs[3]["content"] == "Câu hỏi 3"
    assert openai_msgs[4]["content"] == "Trả lời 3"


def test_session_memory_clear():
    """Kiểm tra reset bộ nhớ nhưng vẫn bảo lưu System Prompt nếu có."""
    mem = SessionMemory(system_prompt="Hệ thống gia sư")
    mem.add_message(MessageRole.USER, "Xin chào")
    assert len(mem.get_messages()) == 1

    mem.clear()
    assert len(mem.get_messages()) == 0
    # to_openai_messages vẫn giữ system prompt
    assert len(mem.to_openai_messages()) == 1
    assert mem.to_openai_messages()[0]["role"] == "system"
