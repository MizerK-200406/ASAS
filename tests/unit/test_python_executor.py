import pytest
from asas.modules.tools.python_executor import PythonExecutorArgs, PythonExecutorTool


@pytest.fixture
def py_tool():
    return PythonExecutorTool(timeout_seconds=2.0)


@pytest.mark.asyncio
async def test_basic_code_execution(py_tool):
    """Kiểm tra thực thi đoạn code Python cơ bản và bắt stdout."""
    code = 'print("Xin chào từ Python Sandbox!")'
    res = await py_tool.execute(code=code)

    assert res.success is True
    assert "Xin chào từ Python Sandbox!" in res.output


@pytest.mark.asyncio
async def test_algorithm_computation(py_tool):
    """Kiểm tra tính toán thuật toán (ví dụ: chuỗi Fibonacci hoặc tính tổng)."""
    code = """
def fib(n):
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a

result = fib(10)
print(f"Fibonacci(10) = {result}")
"""
    res = await py_tool.execute(code=code)
    assert res.success is True
    assert "Fibonacci(10) = 55" in res.output


@pytest.mark.asyncio
async def test_blocks_dangerous_imports(py_tool):
    """Kiểm tra chặn các lệnh import module nguy hiểm (os, sys, subprocess)."""
    code1 = "import os\nprint(os.getcwd())"
    res1 = await py_tool.execute(code=code1)
    assert res1.success is False
    assert "bị cấm" in res1.error.lower() or "không an toàn" in res1.error.lower()

    code2 = "from subprocess import Popen"
    res2 = await py_tool.execute(code=code2)
    assert res2.success is False
    assert res2.error is not None


@pytest.mark.asyncio
async def test_blocks_dunder_traversal(py_tool):
    """Kiểm tra chặn hành vi duyệt thuộc tính dunder (__subclasses__, __globals__)."""
    code = "classes = ().__class__.__bases__[0].__subclasses__()\nprint(classes)"
    res = await py_tool.execute(code=code)
    assert res.success is False
    assert "không an toàn" in res.error.lower() or "dunder" in res.error.lower() or "bị cấm" in res.error.lower()


@pytest.mark.asyncio
async def test_blocks_builtins_like_open_and_eval(py_tool):
    """Kiểm tra chặn việc sử dụng hàm open() hoặc eval()."""
    code = "f = open('requirements.txt', 'r')"
    res = await py_tool.execute(code=code)
    assert res.success is False
    assert res.error is not None


@pytest.mark.asyncio
async def test_timeout_infinite_loop():
    """Kiểm tra ngắt an toàn khi gặp vòng lặp vô tận (timeout)."""
    fast_tool = PythonExecutorTool(timeout_seconds=0.5)
    code = "while True:\n    pass"
    res = await fast_tool.execute(code=code)

    assert res.success is False
    assert "timeout" in res.error.lower() or "thời gian" in res.error.lower()


@pytest.mark.asyncio
async def test_runtime_error_handled(py_tool):
    """Kiểm tra bắt lỗi ngoại lệ trong lúc chạy code (ZeroDivisionError, IndexError)."""
    code = "x = [1, 2, 3]\nprint(x[10])"
    res = await py_tool.execute(code=code)

    assert res.success is False
    assert "IndexError" in res.error
