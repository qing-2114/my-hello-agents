"""第七章：工具链式调用示例。

用法：
    # 仅跑本地计算链，不调用搜索 / LLM
    python -m demos.tool_chain_demo --check
    # 执行搜索 -> 计算 研究链（需要 TAVILY_API_KEY 或 SERPAPI_API_KEY）
    python -m demos.tool_chain_demo
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from dotenv import load_dotenv

from tools.my_calculator_tool import create_calculator_registry
from tools.tool_chain_manager import (
    ToolChainManager,
    create_math_chain,
    create_research_chain,
    create_toolchain_registry,
)


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
        manager = ToolChainManager(registry)
        manager.register_chain(create_math_chain())
        result = manager.execute_chain("double_calculate", "3 + 4")
        print(f"计算链 3 + 4 再乘 2 -> {result}")
        print(f"可用工具链：{manager.list_chains()}")
        return

    load_search_environment()
    registry = create_toolchain_registry()
    manager = ToolChainManager(registry)
    manager.register_chain(create_research_chain())
    answer = manager.execute_chain(
        "research_and_calculate",
        "Python 编程语言是哪一年诞生的",
    )
    print(f"\n工具链最终结果：\n{answer}")
    print(f"可用工具：{registry.list_tools()}")
    print(f"可用工具链：{manager.list_chains()}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="运行工具链式调用示例")
    parser.add_argument(
        "--check",
        action="store_true",
        help="仅运行本地计算链，不调用搜索 API",
    )
    return parser.parse_args()


if __name__ == "__main__":
    run_demo(check_only=parse_args().check)
