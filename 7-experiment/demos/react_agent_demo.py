"""第七章实验：使用改进版 MyReActAgent 运行 ReAct 推理。

用法：
    # 仅检查 .env、工具与 Agent 初始化，不调用 LLM API
    python -m demos.react_agent_demo --check
    # 使用项目根目录 .env 的统一配置发起真实调用
    python -m demos.react_agent_demo

真实调用需要根目录 .env 中的 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL_ID；
配置了 TAVILY_API_KEY 时还会额外注册 search 工具，用于演示「先搜索、再作答」。
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from dotenv import load_dotenv
from hello_agents import HelloAgentsLLM, ToolRegistry
from hello_agents.tools import CalculatorTool, SearchTool

from agents.my_react_agent import MY_REACT_PROMPT, MyReActAgent

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


def build_registry() -> ToolRegistry:
    """构建工具注册表。

    - python_calculator：纯本地计算，无需联网；
    - search：仅在配置了 Tavily/SerpApi 密钥时注册，避免模型拿到必错的工具。
    """
    registry = ToolRegistry()
    registry.register_tool(CalculatorTool())

    if os.getenv("TAVILY_API_KEY") or os.getenv("SERPAPI_API_KEY"):
        registry.register_tool(SearchTool())
    else:
        print("⚠️ 未配置 TAVILY_API_KEY / SERPAPI_API_KEY，本次不注册 search 工具。")
    return registry


def create_agent(max_steps: int = 5) -> MyReActAgent:
    """使用根目录 .env 创建改进版 ReAct Agent。"""
    load_project_environment()
    llm = HelloAgentsLLM()
    registry = build_registry()
    return MyReActAgent(
        name="ReAct助手",
        llm=llm,
        tool_registry=registry,
        max_steps=max_steps,
    )


def run_demo(check_only: bool = False) -> None:
    agent = create_agent()

    if check_only:
        print(
            "配置检查通过："
            f"provider={agent.llm.provider}, model={agent.llm.model}"
        )
        print(f"可用工具：{agent.tool_registry.list_tools()}")
        print(
            "提示词模板："
            + ("MY_REACT_PROMPT（改进版默认）" if agent.prompt_template is MY_REACT_PROMPT
               else "custom_prompt（自定义）")
        )
        return

    # 第 1 问：纯本地计算，走 工具 -> Observation -> Finish 闭环
    answer1 = agent.run(
        "请先调用 python_calculator 计算 (15 + 9) * 3 的结果，"
        "再用中文说明计算过程并给出最终答案。不要自己心算。"
    )
    print(f"\n🧾 最终返回：{answer1}\n")

    # 第 2 问：若注册了 search，则演示联网搜索后再作答
    if "search" in agent.tool_registry.list_tools():
        answer2 = agent.run(
            "请用 search 工具查找 Datawhale「Hello Agents」教程的官网地址，"
            "并简单说明这套教程的主题是什么。"
        )
        print(f"\n🧾 最终返回：{answer2}\n")
    else:
        answer2 = agent.run(
            "请先调用 python_calculator 计算 sqrt(225) + 5 ** 2 的结果，"
            "再用中文给出最终答案。不要自己心算。"
        )
        print(f"\n🧾 最终返回：{answer2}\n")

    print(f"历史消息数：{len(agent.get_history())}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="运行改进版 MyReActAgent 示例")
    parser.add_argument(
        "--check",
        action="store_true",
        help="仅检查 .env 和 Agent 初始化，不调用 LLM API",
    )
    return parser.parse_args()


if __name__ == "__main__":
    run_demo(check_only=parse_args().check)
