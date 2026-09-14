# test_my_advanced_search.py
"""第七章：自定义高级搜索工具的测试。

项目来源：https://hello-agents.datawhale.cc/

保留示例中的 `from my_advanced_search import ...` 写法，因此先把
7-experiment/tools 加入 sys.path。

离线用例只检查空查询，不访问外部服务。真实 Tavily/SerpApi 调用放在
``main()`` 中，由 ``if __name__ == "__main__":`` 触发；``unittest discover``
导入本文件时不会发起搜索请求。

运行真实搜索（读取项目根目录 .env 中的 TAVILY_API_KEY / SERPAPI_API_KEY）：

    F:/my-hello-agent/.conda/python.exe ./7-experiment/tests/test_my_advanced_search.py
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

from my_advanced_search import (  # noqa: E402
    MyAdvancedSearchTool,
    create_advanced_search_registry,
)


class MyAdvancedSearchOfflineTests(unittest.TestCase):
    def test_empty_query(self) -> None:
        tool = MyAdvancedSearchTool()
        self.assertIn("不能为空", tool.search(""))
        self.assertIn("不能为空", tool.search("   "))

    def test_registry_registers_search_function(self) -> None:
        registry = create_advanced_search_registry()
        self.assertIn("advanced_search", registry.list_tools())
        self.assertIn("advanced_search", registry.get_tools_description())
        self.assertIn("不能为空", registry.execute_tool("advanced_search", ""))


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
    """真实搜索冒烟：用 advanced_search 查询 Datawhale Hello Agents。"""
    _load_search_environment()
    registry = create_advanced_search_registry()
    query = "Datawhale Hello Agents"
    print(f"用户问题: {query}")
    result = registry.execute_tool("advanced_search", query)
    print(f"\n搜索结果:\n{result}")
    print(f"可用工具: {registry.list_tools()}")


if __name__ == "__main__":
    main()
