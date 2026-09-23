"""第八章：使用 MemoryTool 添加、搜索和摘要记忆。

项目来源：https://hello-agents.datawhale.cc/

教程示例使用 memory_tool.run("add", content=...)。hello-agents==0.2.0 的
Tool.run 只接受参数字典，因此本 Demo 用 run_memory() 把教程写法适配为
{"action": ..., **kwargs}。

用法：
    # 仅检查根目录 .env 并初始化 MemoryTool / SimpleAgent
    python -m demos.memory_tool_demo --check
    # 真实写入语义记忆、向量检索并生成摘要（Embedding / Qdrant / Neo4j）
    python -m demos.memory_tool_demo
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

EXPERIMENT_DIR = Path(__file__).resolve().parents[1]
if str(EXPERIMENT_DIR) not in sys.path:
    sys.path.insert(0, str(EXPERIMENT_DIR))

from hello_agents import HelloAgentsLLM, SimpleAgent, ToolRegistry
from hello_agents.memory import MemoryConfig
from hello_agents.tools import MemoryTool

from core.config import MEMORY_DATA_DIR, load_project_environment


def run_memory(memory_tool: MemoryTool, action: str, **kwargs: Any) -> str:
    """把教程中的 run("add", content=...) 适配为 0.2.0 的 dict 接口。"""
    return memory_tool.run({"action": action, **kwargs})


def create_memory_agent() -> tuple[SimpleAgent, MemoryTool]:
    """按教程创建带 MemoryTool 的记忆助手。"""
    load_project_environment()

    llm = HelloAgentsLLM()
    memory_tool = MemoryTool(
        user_id="user123",
        memory_config=MemoryConfig(storage_path=str(MEMORY_DATA_DIR)),
    )
    tool_registry = ToolRegistry()
    tool_registry.register_tool(memory_tool)

    agent = SimpleAgent(
        name="记忆助手",
        llm=llm,
        system_prompt="你是一个具有记忆能力的AI助手",
        tool_registry=tool_registry,
    )
    return agent, memory_tool


def run_demo(check_only: bool = False) -> None:
    agent, memory_tool = create_memory_agent()

    if check_only:
        print(
            "配置检查通过："
            f"provider={agent.llm.provider}, model={agent.llm.model}, "
            "tools=memory"
        )
        return

    print("=== 添加多个记忆 ===")

    result1 = run_memory(
        memory_tool,
        "add",
        content="用户张三是一名Python开发者，专注于机器学习和数据分析",
        memory_type="semantic",
        importance=0.8,
    )
    print(f"记忆1: {result1}")

    result2 = run_memory(
        memory_tool,
        "add",
        content="李四是前端工程师，擅长React和Vue.js开发",
        memory_type="semantic",
        importance=0.7,
    )
    print(f"记忆2: {result2}")

    result3 = run_memory(
        memory_tool,
        "add",
        content="王五是产品经理，负责用户体验设计和需求分析",
        memory_type="semantic",
        importance=0.6,
    )
    print(f"记忆3: {result3}")

    print("\n=== 搜索特定记忆 ===")
    print(" 搜索 '前端工程师':")
    result = run_memory(memory_tool, "search", query="前端工程师", limit=3)
    print(result)

    print("\n=== 记忆摘要 ===")
    result = run_memory(memory_tool, "summary")
    print(result)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="运行 MemoryTool 添加、搜索与摘要示例"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="仅检查根目录 .env 和 MemoryTool 初始化，不写入或检索记忆",
    )
    return parser.parse_args()


if __name__ == "__main__":
    run_demo(check_only=parse_args().check)
