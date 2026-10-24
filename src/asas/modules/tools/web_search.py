import asyncio
from typing import Any, Dict, List, Type
from loguru import logger
from pydantic import BaseModel, Field

# Hỗ trợ cả gói ddgs mới và duckduckgo-search cũ
try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS

from asas.core.token_manager import truncate_text_by_tokens
from asas.modules.tools.base import BaseTool, ToolResult


class WebSearchArgs(BaseModel):
    """Tham số đầu vào cho công cụ Web Search."""
    query: str = Field(..., min_length=1, description="Từ khóa hoặc câu hỏi cần tìm kiếm trên internet.")
    max_results: int = Field(default=5, ge=1, le=10, description="Số lượng kết quả tìm kiếm tối đa (1 đến 10).")


class WebSearchTool(BaseTool):
    """Công cụ tìm kiếm thông tin và tài liệu học tập trên internet hoàn toàn miễn phí."""

    name = "web_search"
    description = (
        "Tìm kiếm thông tin cập nhật trên internet qua DuckDuckGo (tin tức, tài liệu học tập, "
        "bài viết công nghệ mới nhất). Hãy sử dụng công cụ này khi cần cập nhật kiến thức mới "
        "hoặc tra cứu các thông tin thực tế ngoài đời thực."
    )
    args_schema: Type[BaseModel] = WebSearchArgs
    max_snippet_tokens: int = 150
    total_budget_tokens: int = 600


    def _raw_search(self, query: str, max_results: int) -> List[Dict[str, str]]:
        """Hàm đồng bộ gọi DuckDuckGo Search API."""
        with DDGS() as ddgs:
            return list(ddgs.text(query, max_results=max_results))

    async def execute(self, query: str = "", max_results: int = 5, **kwargs: Any) -> ToolResult:
        """Thực thi tìm kiếm web bất đồng bộ và format kết quả tối ưu cho LLM."""
        raw_input = {"query": query, "max_results": max_results, **kwargs}
        try:
            validated = self.parse_and_validate_args(raw_input)
            search_query = validated.query.strip()
            num_results = validated.max_results

            logger.info(f"Đang tìm kiếm DuckDuckGo cho từ khóa: '{search_query}' (max_results={num_results})")

            # Chạy hàm tìm kiếm trong thread riêng để tránh chặn event loop
            results = await asyncio.to_thread(self._raw_search, search_query, num_results)

            if not results:
                logger.info(f"Không tìm thấy kết quả nào cho: '{search_query}'")
                return ToolResult(
                    success=True,
                    output=f"Không tìm thấy kết quả nào phù hợp với từ khóa: '{search_query}'.",
                )

            # Format kết quả dạng danh sách dễ đọc cho mô hình AI với giới hạn token an toàn
            formatted_items = []
            for idx, item in enumerate(results, start=1):
                title = item.get("title", "Không có tiêu đề")
                href = item.get("href", "")
                raw_body = item.get("body", "")
                # Cắt gọn nội dung snippet không vượt quá max_snippet_tokens
                body = truncate_text_by_tokens(raw_body, max_tokens=self.max_snippet_tokens)

                formatted_items.append(
                    f"[{idx}] Tiêu đề: {title}\n"
                    f"    Đường dẫn: {href}\n"
                    f"    Tóm tắt: {body}"
                )

            final_output = "\n\n".join(formatted_items)
            # Cắt gọn tổng output nếu vượt quá ngân sách token tối đa cho Web Search
            final_output = truncate_text_by_tokens(final_output, max_tokens=self.total_budget_tokens)

            logger.info(f"Tìm kiếm thành công, trả về {len(results)} kết quả (đã tối ưu hóa token).")
            return ToolResult(success=True, output=final_output)

        except Exception as e:
            logger.error(f"Lỗi khi tìm kiếm web cho '{query}': {e}")
            return ToolResult(success=False, error=f"Lỗi tìm kiếm: {str(e)}")
