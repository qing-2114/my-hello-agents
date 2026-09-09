"""第七章：使用 hello-agents 创建基础对话智能体。"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from dotenv import load_dotenv
from hello_agents import HelloAgentsLLM, SimpleAgent
from hello_agents.tools import CalculatorTool


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


def create_agent() -> SimpleAgent:
    """使用根目录 .env 创建框架自带的 LLM 和 SimpleAgent。"""
    load_project_environment()
    llm = HelloAgentsLLM()
    return SimpleAgent(
        name="AI助手",
        llm=llm,
        system_prompt="你是一个有用的AI助手",
    )


def run_demo(check_only: bool = False) -> None:
    agent = create_agent()

    if check_only:
        print(
            "配置检查通过："
            f"provider={agent.llm.provider}, model={agent.llm.model}"
        )
        return

    response = agent.run("你好！请介绍一下自己")
    print(f"\nAI助手：{response}")

    # hello-agents 0.1.1 的 SimpleAgent 尚未提供 add_tool；这里先完成工具初始化。
    # 后续实现 MySimpleAgent 后，可将 calculator 注册给智能体自主调用。
    calculator = CalculatorTool()
    print(f"\n已初始化工具：{calculator.name}")

    response = agent.run("请帮我计算 2 + 3 * 4")
    print(f"\nAI助手：{response}")
    print(f"\n历史消息数：{len(agent.get_history())}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="运行 hello-agents 基础对话示例")
    parser.add_argument(
        "--check",
        action="store_true",
        help="仅检查根目录 .env 和 Agent 初始化，不调用 LLM API",
    )
    return parser.parse_args()


if __name__ == "__main__":
    run_demo(check_only=parse_args().check)
