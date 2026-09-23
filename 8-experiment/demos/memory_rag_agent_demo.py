"""第八章：带记忆和 RAG 工具的 SimpleAgent。

项目来源：https://hello-agents.datawhale.cc/

用法：
    # 仅检查根目录 .env 并初始化 Agent / 工具，不调用对话 LLM
    python -m demos.memory_rag_agent_demo --check
    # 真实对话：请记住我叫张三，我是一名 Python 开发者
    python -m demos.memory_rag_agent_demo
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

EXPERIMENT_DIR = Path(__file__).resolve().parents[1]
if str(EXPERIMENT_DIR) not in sys.path:
    sys.path.insert(0, str(EXPERIMENT_DIR))

from hello_agents import HelloAgentsLLM, SimpleAgent, ToolRegistry
from hello_agents.memory import MemoryConfig
from hello_agents.tools import MemoryTool, RAGTool

from core.config import (
    KNOWLEDGE_BASE_DIR,
    MEMORY_DATA_DIR,
    load_project_environment,
)


def create_agent() -> SimpleAgent:
    """按教程示例创建带 MemoryTool 和 RAGTool 的 SimpleAgent。"""
    load_project_environment()

    llm = HelloAgentsLLM()
    tool_registry = ToolRegistry()

    memory_tool = MemoryTool(
        user_id="user123",
        memory_config=MemoryConfig(storage_path=str(MEMORY_DATA_DIR)),
    )
    tool_registry.register_tool(memory_tool)

    rag_tool = RAGTool(knowledge_base_path=str(KNOWLEDGE_BASE_DIR))
    if not getattr(rag_tool, "initialized", False):
        raise RuntimeError(
            "RAG 工具初始化失败："
            f"{getattr(rag_tool, 'init_error', '未知错误')}"
        )
    tool_registry.register_tool(rag_tool)

    return SimpleAgent(
        name="智能助手",
        llm=llm,
        system_prompt="你是一个有记忆和知识检索能力的AI助手",
        tool_registry=tool_registry,
    )


def run_demo(check_only: bool = False) -> None:
    agent = create_agent()

    if check_only:
        print(
            "配置检查通过："
            f"provider={agent.llm.provider}, model={agent.llm.model}, "
            "tools=memory,rag"
        )
        return

    response = agent.run("你好！请记住我叫张三，我是一名Python开发者")
    print(response)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="运行带记忆和 RAG 的 SimpleAgent 示例"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="仅检查根目录 .env 和工具初始化，不发起对话 LLM 请求",
    )
    return parser.parse_args()


if __name__ == "__main__":
    run_demo(check_only=parse_args().check)
