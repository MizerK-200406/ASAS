import math
import pytest

from asas.modules.tools.calculator import CalculatorArgs, CalculatorTool


@pytest.fixture
def calc_tool():
    return CalculatorTool()


@pytest.mark.asyncio
async def test_basic_arithmetic(calc_tool):
    """Kiểm tra các phép tính số học cơ bản (+, -, *, /, lũy thừa)."""
    res1 = await calc_tool.execute(expression="2 + 3 * 4")
    assert res1.success is True
    assert float(res1.output) == 14.0

    res2 = await calc_tool.execute(expression="100 / 4 - 5")
    assert res2.success is True
    assert float(res2.output) == 20.0

    res3 = await calc_tool.execute(expression="2 ** 8")
    assert res3.success is True
    assert float(res3.output) == 256.0


@pytest.mark.asyncio
async def test_math_functions_and_constants(calc_tool):
    """Kiểm tra các hàm toán học (sqrt, sin, abs) và hằng số (pi, e)."""
    res1 = await calc_tool.execute(expression="sqrt(144) + 8")
    assert res1.success is True
    assert float(res1.output) == 20.0

    res2 = await calc_tool.execute(expression="abs(-50) + 10")
    assert res2.success is True
    assert float(res2.output) == 60.0

    res3 = await calc_tool.execute(expression="sin(0)")
    assert res3.success is True
    assert float(res3.output) == 0.0

    res4 = await calc_tool.execute(expression="pi")
    assert res4.success is True
    assert pytest.approx(float(res4.output), 0.001) == math.pi


@pytest.mark.asyncio
async def test_division_by_zero(calc_tool):
    """Kiểm tra xử lý lỗi khi chia cho 0 an toàn."""
    res = await calc_tool.execute(expression="50 / 0")
    assert res.success is False
    assert "chia cho 0" in res.error.lower() or "division by zero" in res.error.lower()


@pytest.mark.asyncio
async def test_syntax_error(calc_tool):
    """Kiểm tra xử lý lỗi cú pháp biểu thức toán học."""
    res = await calc_tool.execute(expression="2 + * 3")
    assert res.success is False
    assert res.error is not None
    assert "cú pháp" in res.error.lower() or "syntax" in res.error.lower()


@pytest.mark.asyncio
async def test_security_blocks_malicious_code(calc_tool):
    """Kiểm tra rằng các lệnh gọi hệ thống hoặc truy cập hàm nguy hại đều bị chặn đứng."""
    res1 = await calc_tool.execute(expression="__import__('os').system('ls')")
    assert res1.success is False
    assert res1.error is not None

    res2 = await calc_tool.execute(expression="open('README.md').read()")
    assert res2.success is False
    assert res2.error is not None
