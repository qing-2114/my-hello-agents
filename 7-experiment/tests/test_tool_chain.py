# test_tool_chain.py
"""第七章：工具链式调用测试。

项目来源：https://hello-agents.datawhale.cc/

保留 `from tool_chain_manager import ...` 写法，因此先把
7-experiment/tools 加入 sys.path。

离线用例只跑纯计算链，不访问外部服务。真实搜索链放在 ``main()`` 中，
由 ``if __name__ == "__main__":`` 触发。

运行离线测试：

    F:/my-hello-agent/.conda/python.exe -m unittest discover -s ./7-experiment/tests -p "test_tool_chain.py" -v

运行真实搜索链（读取项目根目录 .env 中的 TAVILY_API_KEY / SERPAPI_API_KEY）：

    F:/my-hello-agent/.conda/python.exe ./7-experiment/tests/test_tool_chain.py
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

from dotenv import load_dotenv

TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"

if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from hello_agents import ToolRegistry  # noqa: E402
from my_calculator_tool import create_calculator_registry  # noqa: E402
from tool_chain_manager import (  # noqa: E402
    ToolChain,
    ToolChainManager,
    create_math_chain,
    create_research_chain,
    create_toolchain_registry,
)


class ToolChainOfflineTests(unittest.TestCase):
    def test_math_chain_passes_result_to_next_step(self) -> None:
        registry = create_calculator_registry()
        manager = ToolChainManager(registry)
        manager.register_chain(create_math_chain())

        result = manager.execute_chain("double_calculate", "3 + 4")

        self.assertEqual(result, "14")
        self.assertEqual(manager.list_chains(), ["double_calculate"])

    def test_missing_template_variable(self) -> None:
        registry = create_calculator_registry()
        chain = ToolChain("broken", "缺少模板变量")
        chain.add_step("my_calculator", "{missing}", "out")
        manager = ToolChainManager(registry)
        manager.register_chain(chain)

        result = manager.execute_chain("broken", "1 + 1")

        self.assertIn("模板变量", result)
        self.assertIn("missing", result)

    def test_unknown_chain(self) -> None:
        manager = ToolChainManager(ToolRegistry())
        result = manager.execute_chain("not_registered", "1")
        self.assertEqual(result, "❌ 工具链 'not_registered' 不存在")

    def test_empty_chain(self) -> None:
        registry = create_calculator_registry()
        chain = ToolChain("empty", "没有步骤")
        result = chain.execute(registry, "1 + 1")
        self.assertEqual(result, "❌ 工具链为空，无法执行")


def _load_search_environment() -> None:
    if not ENV_FILE.is_file():
        raise FileNotFoundError(f"未找到项目环境配置文件：{ENV_FILE}")

    load_dotenv(ENV_FILE)
    if not os.getenv("TAVILY_API_KEY") and not os.getenv("SERPAPI_API_KEY"):
        raise RuntimeError(
            f"真实 API 测试未完成：请在 {ENV_FILE} 中配置 "
            "TAVILY_API_KEY 或 SERPAPI_API_KEY"
        )


def main() -> None:
    """真实 API 冒烟：research_and_calculate 链先搜索再交给计算器。"""
    _load_search_environment()
    registry = create_toolchain_registry()
    manager = ToolChainManager(registry)
    manager.register_chain(create_research_chain())

    query = "Python 编程语言是哪一年诞生的"
    print(f"用户问题: {query}")
    result = manager.execute_chain("research_and_calculate", query)
    print(f"\n工具链最终结果:\n{result}")
    print(f"可用工具: {registry.list_tools()}")
    print(f"可用工具链: {manager.list_chains()}")


if __name__ == "__main__":
    main()
