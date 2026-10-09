import json
import re
from typing import Any, Dict, List, Optional, Type, TypeVar
from openai import AsyncOpenAI, APIError
from pydantic import BaseModel, ValidationError
from loguru import logger

from asas.core.config import Settings, get_settings

T = TypeVar("T", bound=BaseModel)


class LLMClientError(Exception):
    """Lỗi chung xảy ra trong quá trình tương tác với LLM."""
    pass


class LLMParseError(LLMClientError):
    """Lỗi khi không thể parse phản hồi từ LLM sang cấu trúc Schema mong muốn."""
    pass


class LLMClient:
    """Wrapper quản lý kết nối và gọi API tới LLM (tương thích OpenAI / NVIDIA NIM)."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.client = AsyncOpenAI(
            api_key=self.settings.nvidia_api_key,
            base_url=self.settings.nvidia_base_url,
        )

    def _clean_json_text(self, text: str) -> str:
        """Loại bỏ markdown fences (```json ... ```) nếu LLM vô tình bọc lại."""
        text = text.strip()
        # Loại bỏ ```json ở đầu và ``` ở cuối
        pattern = r"^```(?:json)?\s*([\s\S]*?)\s*```$"
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
        return text

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """Gửi prompt và nhận phản hồi dạng văn bản thông thường từ LLM."""
        target_model = model or self.settings.default_model
        try:
            response = await self.client.chat.completions.create(
                model=target_model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            content = response.choices[0].message.content or ""
            return content.strip()
        except APIError as e:
            logger.error(f"Lỗi API khi gọi LLM: {e}")
            raise LLMClientError(f"API Error: {str(e)}") from e
        except Exception as e:
            logger.error(f"Lỗi không xác định khi gọi LLM: {e}")
            raise LLMClientError(f"Unexpected Error: {str(e)}") from e

    async def structured_output(
        self,
        messages: List[Dict[str, str]],
        response_model: Type[T],
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> T:
        """Gửi prompt và ép kiểu đầu ra khớp chính xác với Pydantic Model đã chỉ định."""
        target_model = model or self.settings.default_model

        # Hướng dẫn bổ sung schema vào system prompt để tối đa độ chính xác
        schema_json = json.dumps(response_model.model_json_schema(), ensure_ascii=False)
        schema_instruction = (
            f"\n\nBẠN BẮT BUỘC PHẢI TRẢ VỀ DỮ LIỆU DẠNG JSON HỢP LỆ THEO SCHEMA SAU:\n{schema_json}\n"
            "Chỉ trả về JSON thuần túy, không kèm bất kỳ lời dẫn hay giải thích nào bên ngoài JSON."
        )

        formatted_messages = list(messages)
        # Bổ sung hướng dẫn vào tin nhắn đầu tiên (system hoặc user)
        if formatted_messages and formatted_messages[0]["role"] == "system":
            formatted_messages[0] = {
                "role": "system",
                "content": formatted_messages[0]["content"] + schema_instruction,
            }
        else:
            formatted_messages.insert(
                0,
                {
                    "role": "system",
                    "content": "Bạn là trợ lý AI chuyên nghiệp trả về dữ liệu có cấu trúc JSON." + schema_instruction,
                },
            )

        raw_text = ""
        try:
            response = await self.client.chat.completions.create(
                model=target_model,
                messages=formatted_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
            )
            raw_text = response.choices[0].message.content or ""
            clean_text = self._clean_json_text(raw_text)

            return response_model.model_validate_json(clean_text)
        except (json.JSONDecodeError, ValidationError) as e:
            logger.error(f"Không thể parse dữ liệu từ LLM: {e}. Raw content: {raw_text}")
            raise LLMParseError(f"Không thể parse JSON sang {response_model.__name__}: {str(e)}") from e
        except APIError as e:
            logger.error(f"Lỗi API khi gọi LLM: {e}")
            raise LLMClientError(f"API Error: {str(e)}") from e
        except LLMClientError:
            raise
        except Exception as e:
            logger.error(f"Lỗi ngoài dự kiến: {e}")
            raise LLMClientError(f"Lỗi khi thực thi: {str(e)}") from e
