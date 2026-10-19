from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Type, Union
from pydantic import BaseModel, Field


class ToolResult(BaseModel):
    """Kết quả trả về sau khi thực thi một công cụ (Tool)."""
    success: bool = Field(..., description="Trạng thái thực thi có thành công hay không")
    output: Any = Field(default=None, description="Dữ liệu kết quả của công cụ nếu thành công")
    error: Optional[str] = Field(default=None, description="Chi tiết lỗi nếu thất bại")


class BaseTool(ABC):
    """Lớp cơ sở trừu tượng cho toàn bộ các công cụ (Tools) trong ASAS."""

    name: str = ""
    description: str = ""
    args_schema: Type[BaseModel] = BaseModel

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """Thực thi nghiệp vụ cốt lõi của công cụ với các tham số đã được xác thực."""
        pass

    def to_openai_tool(self) -> Dict[str, Any]:
        """Chuyển đổi thông tin định nghĩa công cụ sang chuẩn OpenAI Function Calling format."""
        if self.args_schema is BaseModel or self.args_schema is None:
            parameters = {"type": "object", "properties": {}}
        else:
            parameters = self.args_schema.model_json_schema()

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": parameters,
            },
        }

    def parse_and_validate_args(self, raw_args: Union[Dict[str, Any], str]) -> BaseModel:
        """Xác thực và parse tham số đầu vào (dạng dict hoặc chuỗi JSON) theo args_schema."""
        if isinstance(raw_args, str):
            return self.args_schema.model_validate_json(raw_args)
        return self.args_schema.model_validate(raw_args)
