"""第七章：使用自定义 my_calculator 工具。

用法：
    # 仅检查本地计算与工具注册，不调用 LLM API
    python -m demos.calculator_tool_demo --check
    # 使用项目根目录 .env 的统一配置，让 MySimpleAgent 真实调用工具
    python -m demos.calculator_tool_demo
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from dotenv import load_dotenv
from hello_agents import HelloAgentsLLM

from agents.my_simple_agent import MySimpleAgent
from tools.my_calculator_tool import create_calculator_registry, my_calculate


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"
REQUIRED_ENV_VARS = ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL_ID")


def load_project_environment() -> None:
    """从项目根目录加载统一的 LLM 配置。"""
    if not ENV_FILE.is_file():
        raise FileNotFoundError(f"未找到项目环境配置文件：{ENV_FILE}")

    load_dotenv(ENV_FILE)
    missing = [name for name in REQUIRED_ENV_VARS if not os.getenv(name)]
    if missing:
        raise RuntimeError(
            f"请在 {ENV_FILE} 中配置以下变量：{', '.join(missing)}"
        )


def create_agent() -> MySimpleAgent:
    """使用根目录 .env 创建带自定义计算器的 MySimpleAgent。"""
    load_project_environment()
    llm = HelloAgentsLLM()
    registry = create_calculator_registry()
    return MySimpleAgent(
        name="计算器助手",
        llm=llm,
        system_prompt="你是一个会使用工具的助手。需要计算时必须调用 my_calculator，不要自己心算。",
        tool_registry=registry,
    )


def run_demo(check_only: bool = False) -> None:
    if check_only:
        print("本地计算检查：")
        print(f"  2 + 3 * 4 -> {my_calculate('2 + 3 * 4')}")
        print(f"  sqrt(16) -> {my_calculate('sqrt(16)')}")
        registry = create_calculator_registry()
        print(f"已注册工具：{registry.list_tools()}")
        print(f"注册表执行：(15 + 9) * 3 -> {registry.execute_tool('my_calculator', '(15 + 9) * 3')}")
        load_project_environment()
        print(
            "配置检查通过："
            f"LLM_MODEL_ID={os.getenv('LLM_MODEL_ID')}"
        )
        return

    agent = create_agent()
    answer = agent.run(
        "请调用 my_calculator 计算 (15 + 9) * 3 的结果，"
        "再用中文给出最终答案。不要自己心算。"
    )
    print(f"\nAI助手：{answer}")
    print(f"可用工具：{agent.list_tools()}")
    print(f"历史消息数：{len(agent.get_history())}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="运行自定义计算器工具示例")
    parser.add_argument(
        "--check",
        action="store_true",
        help="仅检查本地计算、工具注册和根目录 .env，不调用 LLM API",
    )
    return parser.parse_args()


if __name__ == "__main__":
    run_demo(check_only=parse_args().check)
