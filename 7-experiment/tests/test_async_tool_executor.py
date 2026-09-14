# test_async_tool_executor.py
"""第七章：异步并行工具执行器测试。

项目来源：https://hello-agents.datawhale.cc/

保留 `from async_tool_executor import ...` 写法，因此先把
7-experiment/tools 加入 sys.path。

离线用例只并行跑计算器，不访问外部服务。真实搜索 + 计算并行放在
``main()`` 中，由 ``if __name__ == "__main__":`` 触发。

运行离线测试：

    F:/my-hello-agent/.conda/python.exe -m unittest discover -s ./7-experiment/tests -p "test_async_tool_executor.py" -v

运行真实并行搜索（读取项目根目录 .env 中的 TAVILY_API_KEY / SERPAPI_API_KEY）：

    F:/my-hello-agent/.conda/python.exe ./7-experiment/tests/test_async_tool_executor.py
"""

from __future__ import annotations

import asyncio
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

from async_tool_executor import (  # noqa: E402
    AsyncToolExecutor,
    test_parallel_execution,
)
from my_calculator_tool import create_calculator_registry  # noqa: E402


class AsyncToolExecutorOfflineTests(unittest.TestCase):
    def test_parallel_calculator_tasks(self) -> None:
        registry = create_calculator_registry()
        executor = AsyncToolExecutor(registry)
        tasks = [
            {"tool_name": "my_calculator", "input_data": "2 + 2"},
            {"tool_name": "my_calculator", "input_data": "sqrt(16)"},
            {"tool_name": "my_calculator", "input_data": "3 * 4"},
        ]

        try:
            results = asyncio.run(executor.execute_tools_parallel(tasks))
        finally:
            executor.close()

        self.assertEqual(results, ["4", "4.0", "12"])

    def test_unknown_tool_returns_error_string(self) -> None:
        registry = create_calculator_registry()
        executor = AsyncToolExecutor(registry)
        try:
            result = asyncio.run(
                executor.execute_tool_async("not_a_tool", "1 + 1")
            )
        finally:
            executor.close()

        self.assertIn("未找到", result)


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
    """真实 API 冒烟：并行执行两次搜索和两次计算。"""
    _load_search_environment()
    results = asyncio.run(test_parallel_execution())
    print(f"\n共 {len(results)} 个任务结果")
    calc_ok = results[2] == "4" and results[3] == "4.0"
    search_ok = all(
        "Tavily" in item or "SerpApi" in item or "搜索" in item
        for item in results[:2]
    )
    print(f"计算任务通过: {calc_ok}")
    print(f"搜索任务返回了结果: {search_ok}")


if __name__ == "__main__":
    main()
