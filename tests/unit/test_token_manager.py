"""Unit tests for TokenManager: token estimation and budget-aware truncation."""

import pytest
from asas.core.token_manager import (
    estimate_tokens,
    truncate_text_by_tokens,
    truncate_snippets_by_budget,
)


def test_estimate_tokens():
    """Kiểm tra hàm ước lượng số token theo độ dài ký tự và số từ."""
    # Chuỗi rỗng -> 0 token
    assert estimate_tokens("") == 0

    # Chuỗi tiếng Anh
    text_en = "Hello world! This is a test for token estimation."
    tokens_en = estimate_tokens(text_en)
    assert 8 <= tokens_en <= 15

    # Chuỗi tiếng Việt có dấu
    text_vi = "Xin chào các bạn học sinh đang ôn tập cùng hệ thống AI Study Assistant."
    tokens_vi = estimate_tokens(text_vi)
    assert 12 <= tokens_vi <= 25


def test_truncate_text_by_tokens_no_truncation_needed():
    """Nếu văn bản ngắn hơn giới hạn token thì giữ nguyên văn bản."""
    short_text = "Nội dung ngắn gọn."
    result = truncate_text_by_tokens(short_text, max_tokens=100)
    assert result == short_text


def test_truncate_text_by_tokens_truncates_properly():
    """Nếu văn bản vượt quá ngân sách token thì cắt tỉa và thêm dấu ba chấm '...'."""
    long_text = " ".join([f"Từ_thứ_{i}" for i in range(200)])
    max_tokens = 30
    truncated = truncate_text_by_tokens(long_text, max_tokens=max_tokens)

    # Đảm bảo kết quả kết thúc bằng '...'
    assert truncated.endswith("...")
    # Ước lượng token sau khi cắt phải nhỏ hơn hoặc bằng max_tokens
    assert estimate_tokens(truncated) <= max_tokens + 2


def test_truncate_snippets_by_budget():
    """Kiểm tra cắt tỉa danh sách các trích dẫn (search snippets) theo tổng ngân sách token."""
    snippets = [
        "Đây là trích dẫn kết quả tìm kiếm số 1 rất dài chứa nhiều thông tin hữu ích về lập trình Python cơ bản.",
        "Đây là trích dẫn kết quả tìm kiếm số 2 nói về hướng đối tượng OOP và thiết kế module trong dự án phần mềm.",
        "Đây là trích dẫn kết quả tìm kiếm số 3 phân tích sâu về thuật toán sắp xếp và cấu trúc dữ liệu.",
    ]

    # Cắt với ngân sách mỗi snippet tối đa 15 tokens, tổng ngân sách 35 tokens
    trimmed = truncate_snippets_by_budget(
        snippets=snippets,
        max_snippet_tokens=15,
        total_budget_tokens=35,
    )

    assert len(trimmed) <= len(snippets)
    total_tokens = sum(estimate_tokens(s) for s in trimmed)
    assert total_tokens <= 40  # Gần sát tổng ngân sách
