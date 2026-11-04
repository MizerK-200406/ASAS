import json
import pytest
from asas.core.tools import Tool, ToolRegistry, tool


def sample_sync_func(a: int, b: str = "default") -> str:
    """A sample synchronous tool function."""
    return f"Result: {a} - {b}"


async def sample_async_func(x: float, y: float) -> float:
    """A sample asynchronous calculation tool function."""
    return x + y


def test_tool_decorator_sync():
    """Test decorating a sync function to create a Tool."""
    my_tool = tool()(sample_sync_func)

    assert my_tool.name == "sample_sync_func"
    assert "A sample synchronous" in my_tool.description
    assert "properties" in my_tool.parameters_schema
    assert "a" in my_tool.parameters_schema["properties"]

    openai_spec = my_tool.to_openai_tool()
    assert openai_spec["type"] == "function"
    assert openai_spec["function"]["name"] == "sample_sync_func"


@pytest.mark.asyncio
async def test_tool_execution():
    """Test executing sync and async tools safely."""
    sync_tool = tool()(sample_sync_func)
    async_tool = tool(name="add_numbers", description="Add two floats")(sample_async_func)

    res_sync = await sync_tool.execute(a=10, b="test")
    assert res_sync == "Result: 10 - test"

    res_async = await async_tool.execute(x=3.5, y=2.5)
    assert res_async == 6.0


@pytest.mark.asyncio
async def test_tool_registry():
    """Test ToolRegistry registration and tool call execution."""
    registry = ToolRegistry()
    t1 = tool()(sample_sync_func)
    t2 = tool()(sample_async_func)

    registry.register(t1)
    registry.register(t2)

    assert len(registry.list_tools()) == 2
    assert registry.get("sample_sync_func") is not None
    assert registry.get("non_existing") is None

    # Test executing tool call from JSON arguments
    output = await registry.execute_tool_call(
        tool_name="sample_sync_func",
        arguments_json=json.dumps({"a": 42, "b": "hello"}),
    )
    assert output == "Result: 42 - hello"

    # Test invalid JSON handling
    err_output = await registry.execute_tool_call(
        tool_name="sample_sync_func",
        arguments_json="invalid json",
    )
    assert "Error parsing arguments JSON" in err_output

    # Test not found handling
    not_found = await registry.execute_tool_call(
        tool_name="unknown",
        arguments_json="{}",
    )
    assert "not found" in not_found
