"""Framework định nghĩa, đăng ký và thực thi Tool (Công cụ) cho AI Agents.

Được thiết kế sẵn sàng cho Function Calling / Tool Use theo chuẩn OpenAI/NVIDIA API.
"""

from collections.abc import Callable
import inspect
import json
from typing import Any, Dict, List, Optional
from loguru import logger
from pydantic import BaseModel, create_model


class Tool:
    """Đại diện cho một công cụ mà AI Agent có thể gọi."""

    def __init__(
        self,
        name: str,
        description: str,
        func: Callable[..., Any],
        parameters_schema: Dict[str, Any],
    ):
        self.name = name
        self.description = description
        self.func = func
        self.parameters_schema = parameters_schema

    def to_openai_tool(self) -> Dict[str, Any]:
        """Chuyển đổi sang cấu trúc Tool Specification theo chuẩn OpenAI."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema,
            },
        }

    async def execute(self, **kwargs: Any) -> Any:
        """Thực thi hàm đồng bộ hoặc bất đồng bộ một cách an toàn."""
        try:
            if inspect.iscoroutinefunction(self.func):
                return await self.func(**kwargs)
            return self.func(**kwargs)
        except Exception as e:
            logger.error(f"[Tool:{self.name}] Lỗi khi thực thi: {e}")
            return f"Error executing tool '{self.name}': {str(e)}"


class ToolRegistry:
    """Quản lý danh sách các công cụ được cấp quyền cho Agent."""

    def __init__(self) -> None:
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Đăng ký một Tool mới vào hệ thống."""
        self._tools[tool.name] = tool
        logger.debug(f"Đã đăng ký tool: {tool.name}")

    def get(self, name: str) -> Optional[Tool]:
        """Lấy tool theo tên."""
        return self._tools.get(name)

    def list_tools(self) -> List[Tool]:
        """Danh sách tất cả các tool đã đăng ký."""
        return list(self._tools.values())

    def to_openai_tools(self) -> List[Dict[str, Any]]:
        """Xuất danh sách tất cả tool sang định dạng OpenAI tools."""
        return [tool.to_openai_tool() for tool in self._tools.values()]

    async def execute_tool_call(self, tool_name: str, arguments_json: str) -> str:
        """Phân tích arguments và thực thi tool, trả về chuỗi kết quả."""
        tool = self.get(tool_name)
        if not tool:
            return f"Error: Tool '{tool_name}' not found."

        try:
            kwargs = json.loads(arguments_json) if arguments_json else {}
        except json.JSONDecodeError as e:
            return f"Error parsing arguments JSON: {str(e)}"

        result = await tool.execute(**kwargs)
        if isinstance(result, (dict, list, bool, int, float)):
            return json.dumps(result, ensure_ascii=False)
        return str(result)


def tool(name: Optional[str] = None, description: Optional[str] = None) -> Callable[[Callable[..., Any]], Tool]:
    """Decorator biến một hàm Python bất kỳ thành một Tool của AI Agent.

    Tự động trích xuất type hints và docstring của hàm thành JSON Schema.
    """

    def decorator(fn: Callable[..., Any]) -> Tool:
        tool_name = name or fn.__name__
        tool_desc = description or inspect.getdoc(fn) or f"Execute {tool_name}"

        # Trích xuất tham số của hàm để tạo Pydantic model động
        sig = inspect.signature(fn)
        fields: Dict[str, Any] = {}

        for param_name, param in sig.parameters.items():
            if param_name in ("self", "cls"):
                continue
            annotation = param.annotation if param.annotation != inspect.Parameter.empty else Any
            default = param.default if param.default != inspect.Parameter.empty else ...
            fields[param_name] = (annotation, default)

        dynamic_param_model = create_model(f"{tool_name}_params", **fields)  # type: ignore[call-overload]
        schema = dynamic_param_model.model_json_schema()

        # Dọn dẹp schema cho đúng chuẩn OpenAPI Function parameters
        schema.pop("title", None)

        return Tool(
            name=tool_name,
            description=tool_desc.strip(),
            func=fn,
            parameters_schema=schema,
        )

    return decorator
