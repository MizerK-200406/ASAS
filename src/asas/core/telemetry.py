"""Telemetry, latency measurement, and token budget management for LLM calls and operations."""

import time
import uuid
from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager, contextmanager
from datetime import UTC, datetime
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field


def utc_now() -> datetime:
    """Helper trả về thời gian hiện tại chuẩn UTC."""
    return datetime.now(UTC)


class TokenUsage(BaseModel):
    """Thông số token thực tế hoặc ước lượng và chi phí."""

    prompt_tokens: int = Field(default=0, ge=0, description="Số token trong prompt gửi đi")
    completion_tokens: int = Field(default=0, ge=0, description="Số token mô hình sinh ra")
    total_tokens: int = Field(default=0, ge=0, description="Tổng số token tiêu thụ")
    estimated_cost_usd: float = Field(default=0.0, ge=0.0, description="Ước tính chi phí USD nếu có")

    def add(self, other: "TokenUsage") -> "TokenUsage":
        """Cộng dồn thông số token."""
        return TokenUsage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
            estimated_cost_usd=round(self.estimated_cost_usd + other.estimated_cost_usd, 6),
        )


class LatencyMetrics(BaseModel):
    """Đo lường thời gian thực thi (Latency)."""

    start_time: datetime = Field(default_factory=utc_now)
    end_time: datetime | None = None
    duration_ms: float = Field(default=0.0, ge=0.0, description="Thời gian thực thi tính bằng mili-giây")
    is_success: bool = True
    error_type: str | None = None


class LLMExecutionRecord(BaseModel):
    """Bản ghi tổng hợp một phiên gọi LLM hoặc Agent."""

    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str | None = None
    student_id: str | None = None
    model_name: str = ""
    action_type: str = "llm_call"
    tokens: TokenUsage = Field(default_factory=TokenUsage)
    latency: LatencyMetrics = Field(default_factory=LatencyMetrics)
    metadata: dict[str, Any] = Field(default_factory=dict)


@asynccontextmanager
async def track_latency(action_name: str = "operation") -> AsyncGenerator[LatencyMetrics, None]:
    """Async context manager đo lường thời gian thực thi của một tác vụ."""
    metrics = LatencyMetrics(start_time=utc_now())
    start_perf = time.perf_counter()
    try:
        yield metrics
    except Exception as e:
        metrics.is_success = False
        metrics.error_type = type(e).__name__
        raise
    finally:
        metrics.duration_ms = round((time.perf_counter() - start_perf) * 1000, 2)
        metrics.end_time = utc_now()
        logger.debug(f"[{action_name}] Hoàn thành trong {metrics.duration_ms:.2f}ms (Thành công: {metrics.is_success})")


@contextmanager
def track_latency_sync(action_name: str = "operation") -> Generator[LatencyMetrics, None, None]:
    """Sync context manager đo lường thời gian thực thi của một tác vụ đồng bộ."""
    metrics = LatencyMetrics(start_time=utc_now())
    start_perf = time.perf_counter()
    try:
        yield metrics
    except Exception as e:
        metrics.is_success = False
        metrics.error_type = type(e).__name__
        raise
    finally:
        metrics.duration_ms = round((time.perf_counter() - start_perf) * 1000, 2)
        metrics.end_time = utc_now()
        logger.debug(f"[{action_name}] Hoàn thành trong {metrics.duration_ms:.2f}ms (Thành công: {metrics.is_success})")


def estimate_tokens(text: str) -> int:
    """Ước lượng số token của một chuỗi văn bản (hỗ trợ cả Tiếng Anh và Tiếng Việt có dấu).

    Quy ước:
    - Tiếng Anh: ~4 ký tự / token.
    - Tiếng Việt (có dấu): ~3.5 ký tự / token do dấu thanh.
    """
    if not text:
        return 0

    cleaned = text.strip()
    if not cleaned:
        return 0

    char_count = len(cleaned)
    estimated = int(char_count / 3.5)
    return max(1, estimated)


def truncate_text_by_tokens(text: str, max_tokens: int) -> str:
    """Cắt tỉa văn bản theo ngân sách token mà không làm đứt giữa chừng từ ngữ."""
    if not text or max_tokens <= 0:
        return ""

    if estimate_tokens(text) <= max_tokens:
        return text

    words = text.split()
    accumulated_words: list[str] = []

    for word in words:
        candidate = " ".join(accumulated_words + [word])
        if estimate_tokens(candidate) > max_tokens - 1:
            break
        accumulated_words.append(word)

    if not accumulated_words:
        char_limit = max(1, int(max_tokens * 3))
        return text[:char_limit] + "..."

    return " ".join(accumulated_words) + "..."


def truncate_snippets_by_budget(
    snippets: list[str],
    max_snippet_tokens: int = 150,
    total_budget_tokens: int = 600,
) -> list[str]:
    """Cắt tỉa danh sách các đoạn trích tuân thủ ngân sách token tổng."""
    trimmed_snippets: list[str] = []
    current_tokens = 0

    for snippet in snippets:
        if not snippet or not snippet.strip():
            continue

        trimmed = truncate_text_by_tokens(snippet.strip(), max_tokens=max_snippet_tokens)
        snippet_tokens = estimate_tokens(trimmed)

        if current_tokens + snippet_tokens > total_budget_tokens:
            remaining_tokens = total_budget_tokens - current_tokens
            if remaining_tokens > 20:
                partial = truncate_text_by_tokens(trimmed, max_tokens=remaining_tokens)
                trimmed_snippets.append(partial)
            break

        trimmed_snippets.append(trimmed)
        current_tokens += snippet_tokens

    return trimmed_snippets


class UsageTracker:
    """Bộ tích lũy và kiểm soát ngân sách token / thời gian theo session và student."""

    def __init__(self) -> None:
        self._records: list[LLMExecutionRecord] = []

    def record(self, record: LLMExecutionRecord) -> None:
        """Ghi nhận một lượt gọi."""
        self._records.append(record)

    def get_session_usage(self, session_id: str) -> TokenUsage:
        """Lấy tổng số token đã dùng trong một session."""
        total = TokenUsage()
        for r in self._records:
            if r.session_id == session_id:
                total = total.add(r.tokens)
        return total

    def get_session_duration_ms(self, session_id: str) -> float:
        """Lấy tổng thời gian gọi LLM trong một session."""
        return sum(r.latency.duration_ms for r in self._records if r.session_id == session_id)

    def check_budget(self, session_id: str, max_tokens: int) -> bool:
        """Kiểm tra xem session hiện tại có nằm trong ngân sách cho phép không."""
        usage = self.get_session_usage(session_id)
        return usage.total_tokens <= max_tokens

    def clear(self) -> None:
        """Xóa toàn bộ bản ghi theo dõi."""
        self._records.clear()
