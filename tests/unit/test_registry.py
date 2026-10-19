import json
import pytest
from pydantic import BaseModel, Field

from asas.modules.tools.base import BaseTool, ToolResult
from asas.modules.tools.registry import ToolRegistry, create_default_registry


class SimpleArgs(BaseModel):
    text: str = Field(..., description="Văn bản cần xử lý")


class EchoTool(BaseTool):
    name = "echo_tool"
    description = "Công cụ lặp lại văn bản"
    args_schema = SimpleArgs

    async def execute(self, text: str = "", **kwargs) -> ToolResult:
        return ToolResult(success=True, output=f"ECHO: {text}")


@pytest.fixture
def registry():
    reg = ToolRegistry()
    reg.register_tool(EchoTool())
    return reg


def test_register_and_get_tool(registry):
    """Kiểm tra đăng ký công cụ và truy vấn công cụ theo tên."""
    assert registry.has_tool("echo_tool") is True
    assert registry.has_tool("unknown_tool") is False

    tool = registry.get_tool("echo_tool")
    assert tool is not None
    assert tool.name == "echo_tool"

    assert registry.get_tool("unknown_tool") is None


def test_get_openai_tools(registry):
    """Kiểm tra xuất danh sách toàn bộ tool schemas sang chuẩn OpenAI Function Calling."""
    schemas = registry.get_openai_tools()
    assert len(schemas) == 1
    assert schemas[0]["type"] == "function"
    assert schemas[0]["function"]["name"] == "echo_tool"


@pytest.mark.asyncio
async def test_dispatch_execute_success(registry):
    """Kiểm tra điều phối thực thi tool thành công với cả dict và chuỗi JSON."""
    # 1. Truyền tham số dạng dict
    res_dict = await registry.execute_tool(name="echo_tool", arguments={"text": "Xin chào"})
    assert res_dict.success is True
    assert res_dict.output == "ECHO: Xin chào"

    # 2. Truyền tham số dạng chuỗi JSON
    json_args = json.dumps({"text": "Hello JSON"})
    res_json = await registry.execute_tool(name="echo_tool", arguments=json_args)
    assert res_json.success is True
    assert res_json.output == "ECHO: Hello JSON"


@pytest.mark.asyncio
async def test_dispatch_unknown_tool(registry):
    """Kiểm tra điều phối thực thi công cụ không tồn tại."""
    res = await registry.execute_tool(name="missing_tool", arguments={})
    assert res.success is False
    assert "không tồn tại" in res.error.lower()


@pytest.mark.asyncio
async def test_dispatch_invalid_arguments(registry):
    """Kiểm tra điều phối thực thi với tham số không hợp lệ."""
    # Thiếu tham số bắt buộc 'text'
    res = await registry.execute_tool(name="echo_tool", arguments={})
    assert res.success is False
    assert res.error is not None
    assert "validation" in res.error.lower() or "thiếu" in res.error.lower() or "field required" in res.error.lower()


def test_create_default_registry():
    """Kiểm tra tạo Registry mặc định có đủ 3 công cụ: calculator, python_interpreter, web_search."""
    default_reg = create_default_registry()
    assert default_reg.has_tool("calculator") is True
    assert default_reg.has_tool("python_interpreter") is True
    assert default_reg.has_tool("web_search") is True
    assert len(default_reg.get_openai_tools()) == 3
