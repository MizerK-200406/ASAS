import ast
import math
import operator
from typing import Any, Callable, Dict, Type
from loguru import logger
from pydantic import BaseModel, Field

from asas.modules.tools.base import BaseTool, ToolResult

# Danh sách các toán tử an toàn được phép sử dụng
ALLOWED_OPERATORS: Dict[Type[ast.AST], Callable[..., Any]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

# Danh sách hàm và hằng số toán học an toàn
ALLOWED_NAMES: Dict[str, Any] = {
    # Hàm toán học
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "log": math.log,
    "log10": math.log10,
    "log2": math.log2,
    "exp": math.exp,
    "ceil": math.ceil,
    "floor": math.floor,
    "round": round,
    "abs": abs,
    # Hằng số toán học
    "pi": math.pi,
    "e": math.e,
    "tau": math.tau,
}


def _safe_eval_node(node: ast.AST) -> Any:
    """Đệ quy đánh giá cây cú pháp AST của biểu thức toán học trong môi trường cách ly an toàn."""
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float, complex)):
            return node.value
        raise ValueError(f"Giá trị không được hỗ trợ: {node.value}")

    elif isinstance(node, ast.Name):
        if node.id in ALLOWED_NAMES:
            return ALLOWED_NAMES[node.id]
        raise ValueError(f"Ký hiệu không được phép sử dụng: '{node.id}'")

    elif isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type in ALLOWED_OPERATORS:
            left_val = _safe_eval_node(node.left)
            right_val = _safe_eval_node(node.right)
            return ALLOWED_OPERATORS[op_type](left_val, right_val)
        raise ValueError(f"Toán tử hai ngôi không được hỗ trợ: {op_type.__name__}")

    elif isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type in ALLOWED_OPERATORS:
            operand_val = _safe_eval_node(node.operand)
            return ALLOWED_OPERATORS[op_type](operand_val)
        raise ValueError(f"Toán tử một ngôi không được hỗ trợ: {op_type.__name__}")

    elif isinstance(node, ast.Call):
        func = _safe_eval_node(node.func)
        if callable(func):
            args = [_safe_eval_node(arg) for arg in node.args]
            return func(*args)
        raise ValueError("Chỉ được gọi các hàm toán học hợp lệ.")

    else:
        raise ValueError(f"Cấu trúc cú pháp không an toàn hoặc không được phép: {type(node).__name__}")


class CalculatorArgs(BaseModel):
    """Tham số đầu vào cho công cụ Calculator."""
    expression: str = Field(
        ...,
        description="Biểu thức toán học cần tính toán. Ví dụ: '25 * 4 + 10', 'sqrt(144) + 2**3', 'sin(0)', 'pi * 2'",
    )


class CalculatorTool(BaseTool):
    """Công cụ tính toán các biểu thức toán học và số học chính xác tuyệt đối."""

    name = "calculator"
    description = (
        "Thực hiện tính toán các biểu thức toán học hoặc số học chính xác "
        "(cộng, trừ, nhân, chia, lũy thừa, căn bậc hai, hàm lượng giác, logarit). "
        "Hãy sử dụng công cụ này bất cứ khi nào cần giải toán hoặc tính số học để đảm bảo độ chính xác 100%."
    )
    args_schema: Type[BaseModel] = CalculatorArgs

    async def execute(self, expression: str = "", **kwargs: Any) -> ToolResult:
        """Đánh giá và tính toán biểu thức an toàn qua bộ phân tích cú pháp AST."""
        raw_input = {"expression": expression, **kwargs}
        try:
            validated = self.parse_and_validate_args(raw_input)
            expr_str = validated.expression.strip()

            if not expr_str:
                return ToolResult(success=False, error="Biểu thức toán học không được để trống.")

            # Parse chuỗi thành AST dạng expression
            parsed_ast = ast.parse(expr_str, mode="eval")
            result = _safe_eval_node(parsed_ast.body)

            # Format kết quả đẹp: nếu là số nguyên float (vd 20.0), có thể giữ nguyên hoặc format
            output_str = str(result)
            logger.info(f"Calculator tính thành công: '{expr_str}' = {output_str}")

            return ToolResult(success=True, output=output_str)

        except ZeroDivisionError:
            logger.warning(f"Lỗi chia cho 0 trong biểu thức: '{expression}'")
            return ToolResult(success=False, error="Lỗi: Phép chia cho 0 không xác định.")

        except (SyntaxError, ValueError) as e:
            logger.warning(f"Lỗi cú pháp biểu thức toán học '{expression}': {e}")
            return ToolResult(success=False, error=f"Lỗi cú pháp biểu thức toán học: {str(e)}")

        except Exception as e:
            logger.error(f"Lỗi không xác định khi tính toán '{expression}': {e}")
            return ToolResult(success=False, error=f"Lỗi tính toán: {str(e)}")
