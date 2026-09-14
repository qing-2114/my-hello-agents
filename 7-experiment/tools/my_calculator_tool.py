"""第七章实验：自定义计算器工具（函数注册方式）。

项目来源：https://hello-agents.datawhale.cc/

通过 ``ToolRegistry.register_function`` 把纯函数注册为工具，无需继承 ``Tool``。
支持基本四则运算、一元负号、``sqrt`` 函数和常量 ``pi``。
"""

from __future__ import annotations

import ast
import math
import operator
from typing import Any, Callable

from hello_agents import ToolRegistry


# 支持的基本运算（含一元负号，便于解析 -5、2 * -3）
_OPERATORS: dict[type, Callable[..., Any]] = {
    ast.Add: operator.add,  # +
    ast.Sub: operator.sub,  # -
    ast.Mult: operator.mul,  # *
    ast.Div: operator.truediv,  # /
    ast.USub: operator.neg,  # 一元 -
}

# 支持的基本函数与常量
_FUNCTIONS: dict[str, Any] = {
    "sqrt": math.sqrt,
    "pi": math.pi,
}


def my_calculate(expression: str) -> str:
    """简单的数学计算函数。"""
    if not str(expression).strip():
        return "计算表达式不能为空"

    try:
        node = ast.parse(expression.strip(), mode="eval")
        result = _eval_node(node.body, _OPERATORS, _FUNCTIONS)
        return str(result)
    except Exception:
        return "计算失败，请检查表达式格式"


def _eval_node(
    node: ast.AST,
    operators: dict[type, Callable[..., Any]],
    functions: dict[str, Any],
) -> Any:
    """简化的表达式求值。"""
    if isinstance(node, ast.Constant):
        return node.value

    if isinstance(node, ast.UnaryOp):
        op = operators.get(type(node.op))
        if op is None:
            raise ValueError("不支持的运算符")
        return op(_eval_node(node.operand, operators, functions))

    if isinstance(node, ast.BinOp):
        left = _eval_node(node.left, operators, functions)
        right = _eval_node(node.right, operators, functions)
        op = operators.get(type(node.op))
        if op is None:
            raise ValueError("不支持的运算符")
        return op(left, right)

    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise ValueError("不支持的函数调用")
        func_name = node.func.id
        func = functions.get(func_name)
        if not callable(func):
            raise ValueError(f"不支持的函数: {func_name}")
        args = [_eval_node(arg, operators, functions) for arg in node.args]
        return func(*args)

    if isinstance(node, ast.Name):
        if node.id in functions:
            return functions[node.id]
        raise ValueError(f"未定义的变量: {node.id}")

    raise ValueError(f"不支持的表达式类型: {type(node).__name__}")


def create_calculator_registry() -> ToolRegistry:
    """创建包含计算器的工具注册表。"""
    registry = ToolRegistry()
    registry.register_function(
        name="my_calculator",
        description="简单的数学计算工具，支持基本运算(+,-,*,/)和sqrt函数",
        func=my_calculate,
    )
    return registry


if __name__ == "__main__":
    samples = (
        "2 + 3 * 4",
        "sqrt(16)",
        "pi",
        "(15 + 9) * 3",
        "-5 + 3",
        "",
        "2 ** 3",
    )
    for expr in samples:
        print(f"{expr!r} -> {my_calculate(expr)}")

    registry = create_calculator_registry()
    print("可用工具:", registry.list_tools())
    print("registry:", registry.execute_tool("my_calculator", "sqrt(9) + 1"))
