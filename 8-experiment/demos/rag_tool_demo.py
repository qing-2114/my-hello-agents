"""第八章：使用 RAGTool 添加文本、搜索知识并查看统计。

项目来源：https://hello-agents.datawhale.cc/

教程示例使用 rag_tool.execute("add_text", text=...)。hello-agents==0.2.0
的 _preprocess_parameters 会把未传入的 namespace 设成 "default"，覆盖
RAGTool(rag_namespace=...) 的构造参数。本 Demo 用 run_rag() 补上工具自身
的命名空间。

用法：
    # 仅检查根目录 .env 并初始化 RAGTool / SimpleAgent
    python -m demos.rag_tool_demo --check
    # 真实写入三条知识、向量检索并打印知识库统计（Embedding / Qdrant / LLM）
    python -m demos.rag_tool_demo
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
from hello_agents.tools import RAGTool

from core.config import KNOWLEDGE_BASE_DIR, load_project_environment


def run_rag(rag_tool: RAGTool, action: str, **kwargs: Any) -> str:
    """把教程中的 execute("add_text", ...) 接到 0.2.0，并保留 rag_namespace。"""
    if "namespace" not in kwargs or kwargs["namespace"] is None:
        kwargs["namespace"] = rag_tool.rag_namespace
    return rag_tool.execute(action, **kwargs)


def create_rag_agent() -> tuple[SimpleAgent, RAGTool]:
    """按教程创建带 RAGTool 的知识助手。"""
    load_project_environment()

    llm = HelloAgentsLLM()
    rag_tool = RAGTool(
        knowledge_base_path=str(KNOWLEDGE_BASE_DIR),
        collection_name="test_collection",
        rag_namespace="test",
    )
    if not getattr(rag_tool, "initialized", False):
        raise RuntimeError(
            "RAG 工具初始化失败："
            f"{getattr(rag_tool, 'init_error', '未知错误')}"
        )

    tool_registry = ToolRegistry()
    tool_registry.register_tool(rag_tool)

    agent = SimpleAgent(
        name="知识助手",
        llm=llm,
        tool_registry=tool_registry,
    )
    return agent, rag_tool


def run_demo(check_only: bool = False) -> None:
    agent, rag_tool = create_rag_agent()

    if check_only:
        print(
            "配置检查通过："
            f"provider={agent.llm.provider}, model={agent.llm.model}, "
            "tools=rag"
        )
        return

    result1 = run_rag(
        rag_tool,
        "add_text",
        text=(
            "Python是一种高级编程语言，由Guido van Rossum于1991年首次发布。"
            "Python的设计哲学强调代码的可读性和简洁的语法。"
        ),
        document_id="python_intro",
    )
    print(f"知识1: {result1}")

    result2 = run_rag(
        rag_tool,
        "add_text",
        text=(
            "机器学习是人工智能的一个分支，通过算法让计算机从数据中学习模式。"
            "主要包括监督学习、无监督学习和强化学习三种类型。"
        ),
        document_id="ml_basics",
    )
    print(f"知识2: {result2}")

    result3 = run_rag(
        rag_tool,
        "add_text",
        text=(
            "RAG（检索增强生成）是一种结合信息检索和文本生成的AI技术。"
            "它通过检索相关知识来增强大语言模型的生成能力。"
        ),
        document_id="rag_concept",
    )
    print(f"知识3: {result3}")

    print("\n=== 搜索知识 ===")
    result = run_rag(
        rag_tool,
        "search",
        query="Python编程语言的历史",
        limit=3,
        min_score=0.1,
    )
    print(result)

    print("\n=== 知识库统计 ===")
    result = run_rag(rag_tool, "stats")
    print(result)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="运行 RAGTool 添加文本、搜索与统计示例"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="仅检查根目录 .env 和 RAGTool 初始化，不写入或检索知识",
    )
    return parser.parse_args()


if __name__ == "__main__":
    run_demo(check_only=parse_args().check)
