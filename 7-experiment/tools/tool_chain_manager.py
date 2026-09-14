"""第七章实验：工具链式调用。

项目来源：https://hello-agents.datawhale.cc/

把多个已注册工具按顺序串起来，上一步的输出可以通过 ``{output_key}``
写进下一步的输入模板。
"""

from __future__ import annotations

from typing import Any, Optional

from hello_agents import ToolRegistry

try:
    from .my_advanced_search import MyAdvancedSearchTool
    from .my_calculator_tool import my_calculate
except ImportError:  # 直接运行本文件，或把 tools 目录加入 sys.path 时
    from my_advanced_search import MyAdvancedSearchTool
    from my_calculator_tool import my_calculate


class ToolChain:
    """工具链 - 支持多个工具的顺序执行。"""

    def __init__(self, name: str, description: str) -> None:
        self.name = name
        self.description = description
        self.steps: list[dict[str, Any]] = []

    def add_step(
        self,
        tool_name: str,
        input_template: str,
        output_key: Optional[str] = None,
    ) -> None:
        """
        添加工具执行步骤。

        Args:
            tool_name: 工具名称
            input_template: 输入模板，支持变量替换
            output_key: 输出结果的键名，用于后续步骤引用
        """
        self.steps.append(
            {
                "tool_name": tool_name,
                "input_template": input_template,
                "output_key": output_key or f"step_{len(self.steps)}_result",
            }
        )

    def execute(
        self,
        registry: ToolRegistry,
        initial_input: str,
        context: Optional[dict[str, Any]] = None,
    ) -> str:
        """执行工具链。"""
        if not self.steps:
            return "❌ 工具链为空，无法执行"

        context = context or {}
        context["input"] = initial_input

        print(f"开始执行工具链: {self.name}")

        for i, step in enumerate(self.steps, 1):
            tool_name = step["tool_name"]
            input_template = step["input_template"]
            output_key = step["output_key"]

            try:
                tool_input = input_template.format(**context)
            except KeyError as exc:
                return f"❌ 工具链执行失败:模板变量 {exc} 未找到"

            preview = tool_input if len(tool_input) <= 50 else tool_input[:50] + "..."
            print(f"  步骤 {i}: 使用 {tool_name} 处理 {preview!r}")

            result = registry.execute_tool(tool_name, tool_input)
            context[output_key] = result

            print(f"  ✅ 步骤 {i} 完成，结果长度: {len(result)} 字符")

        final_result = context[self.steps[-1]["output_key"]]
        print(f"工具链 '{self.name}' 执行完成")
        return final_result


class ToolChainManager:
    """工具链管理器。"""

    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry
        self.chains: dict[str, ToolChain] = {}

    def register_chain(self, chain: ToolChain) -> None:
        """注册工具链。"""
        self.chains[chain.name] = chain
        print(f"✅ 工具链 '{chain.name}' 已注册")

    def execute_chain(
        self,
        chain_name: str,
        input_data: str,
        context: Optional[dict[str, Any]] = None,
    ) -> str:
        """执行指定的工具链。"""
        if chain_name not in self.chains:
            return f"❌ 工具链 '{chain_name}' 不存在"

        chain = self.chains[chain_name]
        return chain.execute(self.registry, input_data, context)

    def list_chains(self) -> list[str]:
        """列出所有工具链。"""
        return list(self.chains.keys())


def create_toolchain_registry() -> ToolRegistry:
    """创建同时包含计算器和搜索工具的注册表。

    搜索函数额外以教程中的名字 ``search`` 注册，便于 ``create_research_chain``
    直接按示例调用。
    """
    registry = ToolRegistry()
    registry.register_function(
        name="my_calculator",
        description="简单的数学计算工具，支持基本运算(+,-,*,/)和sqrt函数",
        func=my_calculate,
    )

    search_tool = MyAdvancedSearchTool()
    registry.register_function(
        name="search",
        description="智能搜索工具，支持多个搜索源，自动选择最佳结果",
        func=search_tool.search,
    )
    return registry


def create_research_chain() -> ToolChain:
    """创建一个研究工具链:搜索 -> 计算。"""
    chain = ToolChain(
        name="research_and_calculate",
        description="搜索信息并进行相关计算",
    )

    chain.add_step(
        tool_name="search",
        input_template="{input}",
        output_key="search_result",
    )

    chain.add_step(
        tool_name="my_calculator",
        input_template="根据以下信息计算相关数值:{search_result}",
        output_key="calculation_result",
    )

    return chain


def create_math_chain() -> ToolChain:
    """创建一个纯计算工具链:先求值，再把结果乘以 2。"""
    chain = ToolChain(
        name="double_calculate",
        description="先计算表达式，再把结果乘以 2",
    )
    chain.add_step(
        tool_name="my_calculator",
        input_template="{input}",
        output_key="first",
    )
    chain.add_step(
        tool_name="my_calculator",
        input_template="{first} * 2",
        output_key="doubled",
    )
    return chain


if __name__ == "__main__":
    registry = create_toolchain_registry()
    manager = ToolChainManager(registry)
    math_chain = create_math_chain()
    manager.register_chain(math_chain)
    print("可用工具链:", manager.list_chains())
    print(manager.execute_chain("double_calculate", "3 + 4"))
