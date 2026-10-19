from typing import Any, Dict, List, Optional, Union
from loguru import logger
from pydantic import ValidationError

from asas.modules.tools.base import BaseTool, ToolResult
from asas.modules.tools.calculator import CalculatorTool
from asas.modules.tools.python_executor import PythonExecutorTool
from asas.modules.tools.web_search import WebSearchTool


class ToolRegistry:
    """Sổ đăng ký tập trung quản lý và điều phối thực thi các công cụ (Tools)."""

    def __init__(self) -> None:
        self._tools: Dict[str, BaseTool] = {}

    def register_tool(self, tool: BaseTool) -> None:
        """Đăng ký một công cụ mới vào hệ thống."""
        self._tools[tool.name] = tool
        logger.info(f"Đã đăng ký công cụ: '{tool.name}'")

    def has_tool(self, name: str) -> bool:
        """Kiểm tra một công cụ có tồn tại trong hệ thống hay không."""
        return name in self._tools

    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Lấy instance công cụ theo tên định danh."""
        return self._tools.get(name)

    def get_openai_tools(self) -> List[Dict[str, Any]]:
        """Xuất danh sách schema của toàn bộ công cụ đã đăng ký sang chuẩn OpenAI Function Calling."""
        return [tool.to_openai_tool() for tool in self._tools.values()]

    async def execute_tool(
        self, name: str, arguments: Union[Dict[str, Any], str]
    ) -> ToolResult:
        """Điều phối thực thi công cụ theo tên và tham số truyền vào từ LLM."""
        tool = self.get_tool(name)
        if not tool:
            logger.warning(f"Yêu cầu gọi công cụ không tồn tại: '{name}'")
            return ToolResult(
                success=False,
                error=f"Công cụ '{name}' không tồn tại trong hệ thống.",
            )

        try:
            # Xác thực tham số đầu vào với schema Pydantic của công cụ
            validated_args = tool.parse_and_validate_args(arguments)
            args_dict = validated_args.model_dump()

            logger.info(f"Bắt đầu điều phối thực thi công cụ: '{name}'")
            result = await tool.execute(**args_dict)
            return result

        except ValidationError as e:
            logger.warning(f"Lỗi tham số đầu vào khi gọi công cụ '{name}': {e}")
            return ToolResult(
                success=False,
                error=f"Lỗi tham số đầu vào (ValidationError): {str(e)}",
            )
        except Exception as e:
            logger.error(f"Lỗi ngoài dự kiến khi thực thi '{name}': {e}")
            return ToolResult(
                success=False,
                error=f"Lỗi ngoài dự kiến khi thực thi '{name}': {str(e)}",
            )


def create_default_registry() -> ToolRegistry:
    """Khởi tạo một ToolRegistry mặc định tích hợp sẵn bộ ba công cụ cốt lõi của ASAS."""
    registry = ToolRegistry()
    registry.register_tool(CalculatorTool())
    registry.register_tool(PythonExecutorTool())
    registry.register_tool(WebSearchTool())
    return registry
