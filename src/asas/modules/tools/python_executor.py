import ast
import asyncio
import os
import sys
from typing import Any, Dict, Set, Type
from loguru import logger
from pydantic import BaseModel, Field

from asas.modules.tools.base import BaseTool, ToolResult

# Danh sách module hệ thống và mạng bị cấm tuyệt đối
FORBIDDEN_MODULES: Set[str] = {
    "os", "sys", "subprocess", "shutil", "socket", "requests", "urllib",
    "pty", "posix", "nt", "pathlib", "tempfile", "multiprocessing",
    "threading", "ctypes", "builtins", "__builtin__", "importlib", "inspect"
}

# Danh sách các hàm gọi nguy hiểm bị cấm trong sandbox
FORBIDDEN_CALLS: Set[str] = {
    "open", "eval", "exec", "compile", "__import__", "input",
    "exit", "quit", "breakpoint", "help", "globals", "locals", "vars"
}


class SecurityValidator(ast.NodeVisitor):
    """Bộ kiểm tra bảo mật tĩnh dựa trên Abstract Syntax Tree (AST)."""

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            root_module = alias.name.split(".")[0].lower()
            if root_module in FORBIDDEN_MODULES:
                raise ValueError(f"Module '{alias.name}' bị cấm vì lý do an toàn bảo mật.")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            root_module = node.module.split(".")[0].lower()
            if root_module in FORBIDDEN_MODULES:
                raise ValueError(f"Module '{node.module}' bị cấm vì lý do an toàn bảo mật.")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        # Ngăn chặn kỹ thuật sandbox bypass qua dunder attributes
        if node.attr.startswith("__") and node.attr.endswith("__"):
            raise ValueError(f"Truy cập thuộc tính dunder '{node.attr}' bị cấm trong sandbox.")
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id in FORBIDDEN_CALLS:
            raise ValueError(f"Hàm '{node.id}' bị cấm sử dụng trong sandbox.")
        self.generic_visit(node)


class PythonExecutorArgs(BaseModel):
    """Tham số đầu vào cho công cụ Python Executor."""
    code: str = Field(..., description="Đoạn mã nguồn Python cần thực thi.")


class PythonExecutorTool(BaseTool):
    """Công cụ thực thi code Python trong môi trường sandbox an toàn có kiểm soát thời gian (timeout)."""

    name = "python_interpreter"
    description = (
        "Thực thi an toàn đoạn mã Python để tính toán thuật toán, xử lý dữ liệu, "
        "mô phỏng hoặc kiểm tra kết quả logic. "
        "Hãy sử dụng lệnh print() trong đoạn code để xuất kết quả mong muốn."
    )
    args_schema: Type[BaseModel] = PythonExecutorArgs

    def __init__(self, timeout_seconds: float = 2.0):
        self.timeout_seconds = timeout_seconds

    def _build_runner_code(self, user_code: str) -> str:
        """Tạo mã bọc an toàn trước khi chạy trong tiến trình cô lập."""
        return f"""
import math, random, json, re, datetime, collections, itertools

safe_builtins = {{
    "print": print, "range": range, "len": len, "sum": sum, "min": min, "max": max,
    "enumerate": enumerate, "zip": zip, "map": map, "filter": filter, "sorted": sorted,
    "reversed": reversed, "list": list, "dict": dict, "set": set, "tuple": tuple,
    "str": str, "int": int, "float": float, "bool": bool, "abs": abs, "round": round,
    "isinstance": isinstance, "issubclass": issubclass, "all": all, "any": any,
    "pow": pow, "divmod": divmod, "True": True, "False": False, "None": None,
}}

safe_globals = {{
    "__builtins__": safe_builtins,
    "math": math, "random": random, "json": json, "re": re,
    "datetime": datetime, "collections": collections, "itertools": itertools,
}}

safe_locals = {{}}
compiled = compile({repr(user_code)}, "<sandbox>", "exec")
exec(compiled, safe_globals, safe_locals)
"""

    async def execute(self, code: str = "", **kwargs: Any) -> ToolResult:
        """Thực thi mã Python trong tiến trình cách ly OS-level có quản lý timeout."""
        raw_input = {"code": code, **kwargs}
        try:
            validated = self.parse_and_validate_args(raw_input)
            code_str = validated.code.strip()

            if not code_str:
                return ToolResult(success=False, error="Đoạn mã Python không được để trống.")

            # 1. Phân tích cú pháp và kiểm tra an toàn bằng AST
            tree = ast.parse(code_str)
            validator = SecurityValidator()
            validator.visit(tree)

            # 2. Tạo mã bọc runner
            runner_script = self._build_runner_code(code_str)

            # 3. Chạy trong tiến trình con (Process-level isolation)
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"

            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                "-c",
                runner_script,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )

            try:
                stdout_data, stderr_data = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=self.timeout_seconds,
                )
            except asyncio.TimeoutError:
                try:
                    proc.kill()
                    await proc.wait()
                except Exception:
                    pass
                logger.warning(f"Python Sandbox vượt quá timeout ({self.timeout_seconds}s), đã ngắt tiến trình.")
                return ToolResult(
                    success=False,
                    error=f"Thời gian thực thi vượt quá giới hạn cho phép (timeout: {self.timeout_seconds} giây).",
                )

            stdout_str = stdout_data.decode("utf-8", errors="replace").strip()
            stderr_str = stderr_data.decode("utf-8", errors="replace").strip()

            if proc.returncode != 0:
                logger.warning(f"Lỗi runtime trong Python Sandbox: {stderr_str}")
                return ToolResult(success=False, error=stderr_str)

            logger.info(f"Python Sandbox thực thi thành công {len(code_str)} ký tự.")
            final_output = stdout_str if stdout_str else "[Code thực thi thành công nhưng không có output nào được in ra màn hình]"
            return ToolResult(success=True, output=final_output)

        except SyntaxError as e:
            return ToolResult(success=False, error=f"Lỗi cú pháp Python (SyntaxError): {e}")

        except ValueError as e:
            # Lỗi vi phạm bảo mật từ SecurityValidator
            return ToolResult(success=False, error=f"Chặn bảo mật: {str(e)}")

        except Exception as e:
            return ToolResult(success=False, error=f"Lỗi không xác định: {type(e).__name__}: {str(e)}")
