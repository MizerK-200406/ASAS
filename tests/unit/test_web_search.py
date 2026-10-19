from unittest.mock import MagicMock, patch
import pytest
from pydantic import ValidationError

from asas.modules.tools.web_search import WebSearchArgs, WebSearchTool


@pytest.fixture
def search_tool():
    return WebSearchTool()


@pytest.fixture
def sample_ddgs_results():
    return [
        {
            "title": "Python (programming language) - Wikipedia",
            "href": "https://en.wikipedia.org/wiki/Python_(programming_language)",
            "body": "Python is a high-level, general-purpose programming language.",
        },
        {
            "title": "Python Official Documentation",
            "href": "https://docs.python.org/3/",
            "body": "Official documentation for the Python programming language.",
        },
    ]


@pytest.mark.asyncio
async def test_web_search_success(search_tool, sample_ddgs_results):
    """Kiểm tra tìm kiếm web thành công với kết quả trả về được format chuẩn cho LLM."""
    with patch.object(search_tool, "_raw_search", return_value=sample_ddgs_results):
        res = await search_tool.execute(query="Python tutorial", max_results=2)

        assert res.success is True
        assert "Wikipedia" in res.output
        assert "https://docs.python.org/3/" in res.output
        assert "Official documentation" in res.output


@pytest.mark.asyncio
async def test_web_search_empty_results(search_tool):
    """Kiểm tra xử lý êm đẹp khi không tìm thấy kết quả nào."""
    with patch.object(search_tool, "_raw_search", return_value=[]):
        res = await search_tool.execute(query="từ khóa rất hiếm không có thật", max_results=3)

        assert res.success is True
        assert "không tìm thấy" in res.output.lower()


@pytest.mark.asyncio
async def test_web_search_handles_network_error(search_tool):
    """Kiểm tra bắt lỗi mạng hoặc lỗi kết nối từ dịch vụ tìm kiếm."""
    with patch.object(search_tool, "_raw_search", side_effect=Exception("Timeout connecting to search engine")):
        res = await search_tool.execute(query="AI News")

        assert res.success is False
        assert "lỗi tìm kiếm" in res.error.lower()
        assert "timeout" in res.error.lower()


def test_web_search_args_validation(search_tool):
    """Kiểm tra ràng buộc tham số đầu vào của WebSearchArgs."""
    # Hợp lệ
    args = search_tool.parse_and_validate_args({"query": "FastAPI", "max_results": 5})
    assert args.query == "FastAPI"
    assert args.max_results == 5

    # Không hợp lệ: query rỗng
    with pytest.raises(ValidationError):
        search_tool.parse_and_validate_args({"query": "", "max_results": 5})

    # Không hợp lệ: max_results vượt quá giới hạn le=10
    with pytest.raises(ValidationError):
        search_tool.parse_and_validate_args({"query": "AI", "max_results": 25})
