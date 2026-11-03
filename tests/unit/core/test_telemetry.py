import asyncio

import pytest

from asas.core.telemetry import (
    LatencyMetrics,
    LLMExecutionRecord,
    TokenUsage,
    UsageTracker,
    estimate_tokens,
    track_latency,
    track_latency_sync,
    truncate_snippets_by_budget,
    truncate_text_by_tokens,
)


def test_token_usage_addition():
    u1 = TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150, estimated_cost_usd=0.001)
    u2 = TokenUsage(prompt_tokens=50, completion_tokens=25, total_tokens=75, estimated_cost_usd=0.0005)
    total = u1.add(u2)

    assert total.prompt_tokens == 150
    assert total.completion_tokens == 75
    assert total.total_tokens == 225
    assert total.estimated_cost_usd == 0.0015


@pytest.mark.asyncio
async def test_track_latency_async_success():
    async with track_latency("test_async_op") as metrics:
        await asyncio.sleep(0.02)

    assert metrics.is_success is True
    assert metrics.duration_ms >= 15.0
    assert metrics.end_time is not None
    assert metrics.error_type is None


@pytest.mark.asyncio
async def test_track_latency_async_error():
    with pytest.raises(ValueError):
        async with track_latency("failing_op") as metrics:
            await asyncio.sleep(0.01)
            raise ValueError("Something broke")

    assert metrics.is_success is False
    assert metrics.error_type == "ValueError"
    assert metrics.duration_ms >= 5.0


def test_track_latency_sync():
    with track_latency_sync("sync_op") as metrics:
        total = sum(range(1000))
        assert total > 0

    assert metrics.is_success is True
    assert metrics.duration_ms >= 0.0
    assert metrics.end_time is not None


def test_usage_tracker():
    tracker = UsageTracker()
    session_id = "sess_123"

    rec1 = LLMExecutionRecord(
        session_id=session_id,
        action_type="generate_quiz",
        tokens=TokenUsage(prompt_tokens=200, completion_tokens=100, total_tokens=300),
        latency=LatencyMetrics(duration_ms=500.0),
    )
    rec2 = LLMExecutionRecord(
        session_id=session_id,
        action_type="evaluate_quiz",
        tokens=TokenUsage(prompt_tokens=300, completion_tokens=150, total_tokens=450),
        latency=LatencyMetrics(duration_ms=700.0),
    )

    tracker.record(rec1)
    tracker.record(rec2)

    usage = tracker.get_session_usage(session_id)
    assert usage.prompt_tokens == 500
    assert usage.completion_tokens == 250
    assert usage.total_tokens == 750

    duration = tracker.get_session_duration_ms(session_id)
    assert duration == 1200.0

    assert tracker.check_budget(session_id, max_tokens=1000) is True
    assert tracker.check_budget(session_id, max_tokens=500) is False

    tracker.clear()
    assert tracker.get_session_usage(session_id).total_tokens == 0


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

    assert truncated.endswith("...")
    assert estimate_tokens(truncated) <= max_tokens + 2


def test_truncate_snippets_by_budget():
    """Kiểm tra cắt tỉa danh sách các trích dẫn theo tổng ngân sách token."""
    snippets = [
        "Đây là trích dẫn kết quả tìm kiếm số 1 rất dài chứa nhiều thông tin hữu ích về lập trình Python cơ bản.",
        "Đây là trích dẫn kết quả tìm kiếm số 2 nói về hướng đối tượng OOP và thiết kế module trong dự án phần mềm.",
        "Đây là trích dẫn kết quả tìm kiếm số 3 phân tích sâu về thuật toán sắp xếp và cấu trúc dữ liệu.",
    ]

    trimmed = truncate_snippets_by_budget(
        snippets=snippets,
        max_snippet_tokens=15,
        total_budget_tokens=35,
    )

    assert len(trimmed) <= len(snippets)
    total_tokens = sum(estimate_tokens(s) for s in trimmed)
    assert total_tokens <= 40
