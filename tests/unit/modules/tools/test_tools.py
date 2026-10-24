import json
from typing import Type
import pytest
from pydantic import BaseModel, Field, ValidationError

from asas.modules.tools.base import BaseTool, ToolResult


class DummyArgs(BaseModel):
    query: str = Field(..., description="Từ khóa tìm kiếm")
    limit: int = Field(default=5, ge=1, le=10, description="Số lượng kết quả tối đa")


class DummyTool(BaseTool):
    name = "dummy_search"
    description = "Công cụ tìm kiếm giả lập dùng cho kiểm thử."
    args_schema: Type[BaseModel] = DummyArgs

    async def execute(self, **kwargs) -> ToolResult:
        validated = self.args_schema(**kwargs)
        return ToolResult(
            success=True,
            output=f"Tìm thấy kết quả cho '{validated.query}' với giới hạn {validated.limit}",
        )


def test_tool_result_model():
    """Kiểm tra khởi tạo mô hình ToolResult với trạng thái thành công và lỗi."""
    success_res = ToolResult(success=True, output="Kết quả thành công")
    assert success_res.success is True
    assert success_res.output == "Kết quả thành công"
    assert success_res.error is None

    fail_res = ToolResult(success=False, output=None, error="Lỗi timeout")
    assert fail_res.success is False
    assert fail_res.error == "Lỗi timeout"


def test_subclass_without_execute_raises_type_error():
    """Kiểm tra rằng lớp kế thừa BaseTool nếu không cài đặt execute() sẽ không thể khởi tạo."""
    class IncompleteTool(BaseTool):
        name = "incomplete"
        description = "Chưa có hàm execute"
        args_schema = DummyArgs

    with pytest.raises(TypeError):
        IncompleteTool()


def test_to_openai_tool_format():
    """Kiểm tra việc xuất schema công cụ sang chuẩn OpenAI Function Calling format."""
    tool = DummyTool()
    openai_tool = tool.to_openai_tool()

    assert openai_tool["type"] == "function"
    assert "function" in openai_tool

    func_def = openai_tool["function"]
    assert func_def["name"] == "dummy_search"
    assert func_def["description"] == "Công cụ tìm kiếm giả lập dùng cho kiểm thử."
    assert "parameters" in func_def

    params = func_def["parameters"]
    assert "properties" in params
    assert "query" in params["properties"]
    assert "limit" in params["properties"]
    assert "required" in params
    assert "query" in params["required"]


@pytest.mark.asyncio
async def test_dummy_tool_execution():
    """Kiểm tra thực thi bất đồng bộ của DummyTool."""
    tool = DummyTool()
    res = await tool.execute(query="Machine Learning", limit=3)

    assert isinstance(res, ToolResult)
    assert res.success is True
    assert "Machine Learning" in res.output
    assert "3" in res.output


def test_parse_and_validate_args():
    """Kiểm tra hàm parse_and_validate_args với dict và chuỗi JSON."""
    tool = DummyTool()

    # Hợp lệ với dict
    args_dict = tool.parse_and_validate_args({"query": "Python", "limit": 4})
    assert isinstance(args_dict, DummyArgs)
    assert args_dict.query == "Python"
    assert args_dict.limit == 4

    # Hợp lệ với chuỗi JSON
    json_str = json.dumps({"query": "FastAPI"})
    args_json = tool.parse_and_validate_args(json_str)
    assert args_json.query == "FastAPI"
    assert args_json.limit == 5  # default value

    # Không hợp lệ: thiếu tham số bắt buộc 'query'
    with pytest.raises(ValidationError):
        tool.parse_and_validate_args({"limit": 5})

    # Không hợp lệ: limit vượt quá giới hạn le=10
    with pytest.raises(ValidationError):
        tool.parse_and_validate_args({"query": "AI", "limit": 20})
