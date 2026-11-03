import json
import re
from typing import Any, Dict, List, Optional, Type, TypeVar
from openai import AsyncOpenAI, APIError
from pydantic import BaseModel, ValidationError
from loguru import logger

from asas.core.config import Settings, get_settings
from asas.core.telemetry import (
    LatencyMetrics,
    LLMExecutionRecord,
    TokenUsage,
    UsageTracker,
    estimate_tokens,
    track_latency,
)

T = TypeVar("T", bound=BaseModel)


class LLMClientError(Exception):
    """Lỗi chung xảy ra trong quá trình tương tác với LLM."""
    pass


class LLMParseError(LLMClientError):
    """Lỗi khi không thể parse phản hồi từ LLM sang cấu trúc Schema mong muốn."""
    pass


class LLMClient:
    """Wrapper quản lý kết nối và gọi API tới LLM (tương thích OpenAI / NVIDIA NIM)."""

    settings: Settings
    client: AsyncOpenAI
    usage_tracker: UsageTracker
    last_execution_record: Optional[LLMExecutionRecord]

    def __init__(
        self,
        settings: Optional[Settings] = None,
        usage_tracker: Optional[UsageTracker] = None,
    ):
        self.settings = settings or get_settings()
        self.client = AsyncOpenAI(
            api_key=self.settings.nvidia_api_key,
            base_url=self.settings.nvidia_base_url,
            timeout=60.0,
        )
        self.usage_tracker = usage_tracker or UsageTracker()
        self.last_execution_record: Optional[LLMExecutionRecord] = None

    def _clean_json_text(self, text: str) -> str:
        """Loại bỏ markdown fences (```json ... ```) hoặc trích xuất khối JSON từ phản hồi."""
        text = text.strip()
        # 1. Tìm khối markdown ```json ... ```
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if match:
            return match.group(1).strip()
        # 2. Nếu không có markdown fences, trích xuất từ dấu { đầu tiên đến } cuối cùng
        start_obj = text.find("{")
        end_obj = text.rfind("}")
        if start_obj != -1 and end_obj != -1 and end_obj > start_obj:
            return text[start_obj : end_obj + 1].strip()
        return text

    def _repair_truncated_json(self, text: str) -> str:
        """Tự động vá chuỗi JSON bị ngắt cụt do chạm trần token hoặc lỗi kết thúc lửng lơ."""
        text = text.strip()
        start_idx = text.find("{")
        if start_idx == -1:
            return text
        text = text[start_idx:]

        # Nếu đã là JSON hợp lệ thì trả về luôn
        try:
            json.loads(text)
            return text
        except json.JSONDecodeError:
            pass

        # Chiến lược 1: Cắt bỏ phần tử dở dang cuối cùng trong mảng đối tượng
        last_closed_brace = text.rfind("}")
        if last_closed_brace != -1:
            truncated = text[: last_closed_brace + 1].strip()
            if truncated.endswith(","):
                truncated = truncated[:-1].strip()

            for suffix in ["]}", "\n  ]\n}", "}"]:
                candidate = truncated + suffix
                try:
                    json.loads(candidate)
                    logger.warning(f"Đã tự động phục hồi JSON bị cắt cụt bằng hậu tố '{suffix}'.")
                    return candidate
                except json.JSONDecodeError:
                    continue

        # Chiến lược 2: Cân bằng ngoặc LIFO nếu chuỗi kết thúc trong string/object
        stack = []
        in_string = False
        escape = False

        for char in text:
            if char == '"' and not escape:
                in_string = not in_string
            elif not in_string:
                if char in "{[":
                    stack.append(char)
                elif char in "}]" and stack:
                    top = stack[-1]
                    if (top == "{" and char == "}") or (top == "[" and char == "]"):
                        stack.pop()

            escape = (char == "\\" and not escape)

        repaired = text
        if in_string:
            repaired += '"'

        closers = {"{": "}", "[": "]"}
        for opener in reversed(stack):
            repaired += closers[opener]

        try:
            json.loads(repaired)
            logger.warning("Đã tự động cân bằng ngoặc cho chuỗi JSON bị ngắt cụt.")
            return repaired
        except json.JSONDecodeError:
            pass

        return text

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 2048,
        session_id: Optional[str] = None,
        student_id: Optional[str] = None,
        action_type: str = "chat_completion",
    ) -> str:
        """Gửi prompt và nhận phản hồi dạng văn bản thông thường từ LLM kèm telemetry."""
        target_model = model or self.settings.default_model
        async with track_latency(action_type) as latency:
            try:
                response = await self.client.chat.completions.create(
                    model=target_model,
                    messages=messages,  # type: ignore[arg-type]
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                message = response.choices[0].message
                content = message.content or getattr(message, "reasoning_content", "") or ""

                # Trích xuất hoặc ước lượng token usage
                usage = getattr(response, "usage", None)
                if usage and hasattr(usage, "prompt_tokens") and isinstance(usage.prompt_tokens, int):
                    tokens = TokenUsage(
                        prompt_tokens=usage.prompt_tokens,
                        completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
                        total_tokens=getattr(usage, "total_tokens", 0) or 0,
                    )
                else:
                    p_len = sum(estimate_tokens(m.get("content", "")) for m in messages)
                    c_len = estimate_tokens(content)
                    tokens = TokenUsage(prompt_tokens=p_len, completion_tokens=c_len, total_tokens=p_len + c_len)

                rec = LLMExecutionRecord(
                    session_id=session_id,
                    student_id=student_id,
                    model_name=target_model,
                    action_type=action_type,
                    tokens=tokens,
                    latency=latency,
                )
                self.last_execution_record = rec
                self.usage_tracker.record(rec)

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
        system_prompt: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        session_id: Optional[str] = None,
        student_id: Optional[str] = None,
        action_type: str = "structured_output",
    ) -> T:
        """Gửi prompt và ép kiểu đầu ra khớp chính xác với Pydantic Model đã chỉ định kèm telemetry."""
        target_model = model or self.settings.default_model

        # Hướng dẫn bổ sung schema vào system prompt để tối đa độ chính xác
        schema_json = json.dumps(response_model.model_json_schema(), ensure_ascii=False)
        schema_instruction = (
            f"\n\nBẠN BẮT BUỘC PHẢI TRẢ VỀ DỮ LIỆU DẠNG JSON HỢP LỆ THEO SCHEMA SAU:\n{schema_json}\n"
            "Chỉ trả về JSON thuần túy, không kèm bất kỳ lời dẫn hay giải thích nào bên ngoài JSON."
        )

        formatted_messages = list(messages)
        # Bổ sung hướng dẫn vào tin nhắn system đầu tiên
        if system_prompt:
            formatted_messages.insert(
                0,
                {
                    "role": "system",
                    "content": system_prompt + schema_instruction,
                },
            )
        elif formatted_messages and formatted_messages[0]["role"] == "system":
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

        current_temp = temperature
        last_error: Optional[Exception] = None

        async with track_latency(action_type) as latency:
            for attempt in range(2):
                raw_text = ""
                try:
                    response = await self.client.chat.completions.create(
                        model=target_model,
                        messages=formatted_messages,  # type: ignore[arg-type]
                        temperature=current_temp,
                        max_tokens=max_tokens,
                    )
                    choice = response.choices[0]
                    finish_reason = getattr(choice, "finish_reason", None)
                    if finish_reason == "length":
                        logger.warning(
                            f"LLM phản hồi chạm trần max_tokens ({max_tokens}). Sẽ kích hoạt cơ chế tự phục hồi JSON nếu cần."
                        )

                    message = choice.message
                    content_text = message.content or ""
                    reasoning_text = getattr(message, "reasoning_content", "") or ""

                    # Ưu tiên lấy từ content nếu có chứa ký tự JSON
                    if "{" in content_text and "}" in content_text:
                        raw_text = content_text
                    elif "{" in reasoning_text and "}" in reasoning_text:
                        raw_text = reasoning_text
                    else:
                        raw_text = content_text or reasoning_text

                    clean_text = self._clean_json_text(raw_text)

                    # Trích xuất usage token
                    usage = getattr(response, "usage", None)
                    if usage and hasattr(usage, "prompt_tokens") and isinstance(usage.prompt_tokens, int):
                        tokens = TokenUsage(
                            prompt_tokens=usage.prompt_tokens,
                            completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
                            total_tokens=getattr(usage, "total_tokens", 0) or 0,
                        )
                    else:
                        p_len = sum(estimate_tokens(m.get("content", "")) for m in formatted_messages)
                        c_len = estimate_tokens(clean_text)
                        tokens = TokenUsage(prompt_tokens=p_len, completion_tokens=c_len, total_tokens=p_len + c_len)

                    try:
                        validated = response_model.model_validate_json(clean_text)
                    except (json.JSONDecodeError, ValidationError):
                        # Kích hoạt cơ chế tự động sửa lỗi JSON bị cắt cụt
                        repaired_text = self._repair_truncated_json(raw_text)
                        if repaired_text != clean_text:
                            try:
                                validated = response_model.model_validate_json(repaired_text)
                            except (json.JSONDecodeError, ValidationError):
                                raise
                        else:
                            raise

                    # Ghi nhận record telemetry khi thành công
                    rec = LLMExecutionRecord(
                        session_id=session_id,
                        student_id=student_id,
                        model_name=target_model,
                        action_type=action_type,
                        tokens=tokens,
                        latency=latency,
                    )
                    self.last_execution_record = rec
                    self.usage_tracker.record(rec)
                    return validated

                except (json.JSONDecodeError, ValidationError) as e:
                    last_error = e
                    if attempt == 0:
                        logger.warning(
                            f"[LLMClient] Lần 1 không thể parse JSON ({e}). Tự động thử lại với lời nhắc xuất JSON trực tiếp..."
                        )
                        formatted_messages.append({
                            "role": "user",
                            "content": "LƯU Ý QUAN TRỌNG: Hãy bỏ qua toàn bộ suy nghĩ (reasoning) dài dòng. Xuất NGAY LẬP TỨC toàn bộ dữ liệu dưới dạng JSON hợp lệ theo schema.",
                        })
                        current_temp = 0.1
                        continue
                    logger.error(f"Không thể parse dữ liệu từ LLM sau {attempt + 1} lần thử: {e}. Raw content: {raw_text[:500]}...")
                    raise LLMParseError(f"Không thể parse JSON sang {response_model.__name__}: {str(e)}") from e
                except APIError as e:
                    logger.error(f"Lỗi API khi gọi LLM: {e}")
                    raise LLMClientError(f"API Error: {str(e)}") from e
                except LLMClientError:
                    raise
                except Exception as e:
                    logger.error(f"Lỗi ngoài dự kiến: {e}")
                    raise LLMClientError(f"Lỗi khi thực thi: {str(e)}") from e

            if last_error:
                raise LLMParseError(f"Không thể parse JSON sang {response_model.__name__}: {str(last_error)}") from last_error
            raise LLMClientError("Không nhận được phản hồi hợp lệ từ mô hình.")
