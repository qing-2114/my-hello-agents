"""第七章：异步并行工具执行示例。

用法：
    # 仅并行跑计算器，不调用搜索
    python -m demos.async_tool_demo --check
    # 并行执行两次搜索和两次计算（需要 TAVILY_API_KEY 或 SERPAPI_API_KEY）
    python -m demos.async_tool_demo
"""

from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

from tools.async_tool_executor import AsyncToolExecutor, test_parallel_execution
from tools.my_calculator_tool import create_calculator_registry


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"


def load_search_environment() -> None:
    """从项目根目录加载搜索相关配置。"""
    if not ENV_FILE.is_file():
        raise FileNotFoundError(f"未找到项目环境配置文件：{ENV_FILE}")

    load_dotenv(ENV_FILE)
    if not os.getenv("TAVILY_API_KEY") and not os.getenv("SERPAPI_API_KEY"):
        raise RuntimeError(
            f"请在 {ENV_FILE} 中配置 TAVILY_API_KEY 或 SERPAPI_API_KEY"
        )


def run_demo(check_only: bool = False) -> None:
    if check_only:
        registry = create_calculator_registry()
        executor = AsyncToolExecutor(registry)
        tasks = [
            {"tool_name": "my_calculator", "input_data": "2 + 2"},
            {"tool_name": "my_calculator", "input_data": "sqrt(16)"},
        ]
        try:
            results = asyncio.run(executor.execute_tools_parallel(tasks))
        finally:
            executor.close()
        print(f"并行计算结果：{results}")
        return

    load_search_environment()
    results = asyncio.run(test_parallel_execution())
    print(f"\n共 {len(results)} 个任务结果")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="运行异步并行工具执行示例")
    parser.add_argument(
        "--check",
        action="store_true",
        help="仅并行运行计算器，不调用搜索 API",
    )
    return parser.parse_args()


if __name__ == "__main__":
    run_demo(check_only=parse_args().check)
