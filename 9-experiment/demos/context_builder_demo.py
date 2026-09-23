"""第九章实验：用 ContextBuilder 构建 GSSC 上下文（教程示例的可运行版本）。

项目来源：https://hello-agents.datawhale.cc/

流程（与教程示例一致）：
1. 初始化 MemoryTool（语义 + 情景记忆）与 RAGTool（本章独立命名空间）
2. 清理并写入实验记忆：语义 1 条 + 情景 1 条
3. 把 knowledge_base/pandas_memory_optimization.md 写入 RAG
4. 准备 4 轮对话历史
5. ContextBuilder.build(...) 构建上下文并打印（Gather-Select-Structure-Compress）
6. 把构建好的上下文整体交给 LLM 回答，验证端到端效果

用法（在 9-experiment 目录下）：
    # 仅检查 .env 与工具初始化（含 Qdrant / Neo4j / Embedding 连通），不发起对话
    F:\\my-hello-agent\\.conda\\python.exe -m demos.context_builder_demo --check
    # 完整实验：写入数据 -> 构建上下文 -> 调用 LLM 回答
    F:\\my-hello-agent\\.conda\\python.exe -m demos.context_builder_demo
    # 复现教程原始配置（min_relevance=0.2，观察非系统包被全部过滤）
    F:\\my-hello-agent\\.conda\\python.exe -m demos.context_builder_demo --min-relevance 0.2
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from datetime import datetime
from pathlib import Path

EXPERIMENT_DIR = Path(__file__).resolve().parents[1]
if str(EXPERIMENT_DIR) not in sys.path:
    sys.path.insert(0, str(EXPERIMENT_DIR))

from hello_agents import HelloAgentsLLM
from hello_agents.context import ContextBuilder, ContextConfig
from hello_agents.context.builder import count_tokens
from hello_agents.core.message import Message
from hello_agents.memory import MemoryConfig
from hello_agents.tools import MemoryTool

from core.chapter9_tools import (
    DEMO_USER_ID,
    RAG_COLLECTION,
    RAG_NAMESPACE,
    Chapter9RAGTool,
    purge_user_memories,
    seed_knowledge_base,
    seed_memories,
)
from core.config import KNOWLEDGE_BASE_DIR, MEMORY_DATA_DIR, load_project_environment

SEPARATOR = "=" * 80

USER_QUERY = "如何优化Pandas的内存占用?"

SYSTEM_INSTRUCTIONS = (
    "你是一位资深的Python数据工程顾问。你的回答需要:"
    "1) 提供具体可行的建议 2) 解释技术原理 3) 给出代码示例"
)

CONVERSATION_HISTORY = [
    Message(content="我正在开发一个数据分析工具", role="user", timestamp=datetime.now()),
    Message(
        content="很好!数据分析工具通常需要处理大量数据。您计划使用什么技术栈?",
        role="assistant",
        timestamp=datetime.now(),
    ),
    Message(
        content="我打算使用Python和Pandas,已经完成了CSV读取模块",
        role="user",
        timestamp=datetime.now(),
    ),
    Message(
        content="不错的选择!Pandas在数据处理方面非常强大。接下来您可能需要考虑数据清洗和转换。",
        role="assistant",
        timestamp=datetime.now(),
    ),
]


def create_tools():
    """按教程示例初始化 MemoryTool 与 RAGTool。"""
    load_project_environment()

    memory_tool = MemoryTool(
        user_id=DEMO_USER_ID,
        memory_config=MemoryConfig(storage_path=str(MEMORY_DATA_DIR)),
    )
    rag_tool = Chapter9RAGTool(
        knowledge_base_path=str(KNOWLEDGE_BASE_DIR),
        collection_name=RAG_COLLECTION,
        rag_namespace=RAG_NAMESPACE,
    )
    if not getattr(rag_tool, "initialized", False):
        raise RuntimeError(
            "RAG 工具初始化失败："
            f"{getattr(rag_tool, 'init_error', '未知错误')}"
        )
    return memory_tool, rag_tool


def prepare_data(memory_tool: MemoryTool, rag_tool: Chapter9RAGTool) -> None:
    """清理历史数据并写入本实验的记忆与知识库文档。"""
    purged = purge_user_memories(memory_tool, DEMO_USER_ID)
    print(
        "   清理上次运行遗留："
        f"Qdrant 向量 {purged['qdrant_vectors']} 条，"
        f"SQLite 情景记忆 {purged['episodic_docs']} 条"
    )

    for line in seed_memories(memory_tool):
        print(f"   {line}")

    print(f"   {seed_knowledge_base(rag_tool)}")


def build_context(
    memory_tool: MemoryTool,
    rag_tool: Chapter9RAGTool,
    min_relevance: float,
) -> str:
    """构建 GSSC 上下文（教程示例 + 修正后的相关性阈值）。"""
    config = ContextConfig(
        max_tokens=3000,
        reserve_ratio=0.2,
        min_relevance=min_relevance,
        enable_compression=True,
    )
    builder = ContextBuilder(
        memory_tool=memory_tool,
        rag_tool=rag_tool,
        config=config,
    )
    return builder.build(
        user_query=USER_QUERY,
        conversation_history=CONVERSATION_HISTORY,
        system_instructions=SYSTEM_INSTRUCTIONS,
    )


def summarize_context(context: str) -> None:
    """打印上下文的分区与 token 统计。"""
    sections = []
    for block in split_sections(context):
        name = block.split("]", 1)[0] + "]"
        sections.append(f"{name} {count_tokens(block)} tokens")
    print(f"   总 token 数：{count_tokens(context)}")
    print(f"   分区：{' | '.join(sections)}")


def split_sections(context: str) -> list[str]:
    """按分区切分上下文，返回各分区完整文本。

    框架用空行连接各分区，因此以「空行 + 行首 [」为边界；
    对话历史里的 [user] / [assistant] 行没有前置空行，不会被误切。
    """
    blocks = re.split(r"\n\n(?=\[)", context)
    return [block.strip() for block in blocks if block.strip().startswith("[")]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ContextBuilder 上下文构建实例")
    parser.add_argument(
        "--check",
        action="store_true",
        help="仅检查根目录 .env 与工具初始化，不发起对话 LLM 请求",
    )
    parser.add_argument(
        "--min-relevance",
        type=float,
        default=0.0,
        help=(
            "Select 阶段的最小相关性阈值（默认 0.0）。"
            "hello-agents 0.2.8 按空格分词计算相关性，中文查询（无空格）时"
            "所有非系统包相关性为 0，教程默认值 0.2 会把它们全部过滤；"
            "传入 0.2 可复现该现象，详见 README「实测发现」。"
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    print(SEPARATOR)
    print("[1/4] 初始化工具")
    print(SEPARATOR)
    memory_tool, rag_tool = create_tools()
    print(f"   ✅ 记忆工具就绪：user_id={DEMO_USER_ID}，记忆类型={memory_tool.memory_types}")
    print(
        f"   ✅ RAG 工具就绪：namespace={RAG_NAMESPACE}, collection={RAG_COLLECTION}，"
        f"provider={rag_tool.llm.provider}, model={rag_tool.llm.model}"
    )

    if args.check:
        print("\n配置检查通过（--check 模式不发起对话 LLM 请求）")
        return

    if args.min_relevance > 0:
        print(
            f"\n   ℹ️ min_relevance={args.min_relevance}：按 0.2.8 的分词方式，"
            "中文查询的相关性恒为 0，非系统包会被全部过滤"
            "（[State]/[Evidence]/[Context] 不出现），见 README「实测发现」。"
        )

    print(f"\n{SEPARATOR}")
    print("[2/4] 写入实验数据（记忆 + 知识库）")
    print(SEPARATOR)
    prepare_data(memory_tool, rag_tool)

    print(f"\n{SEPARATOR}")
    print("[3/4] 构建上下文（Gather-Select-Structure-Compress）")
    print(SEPARATOR)
    started = time.time()
    context = build_context(memory_tool, rag_tool, args.min_relevance)
    elapsed = time.time() - started

    print(SEPARATOR)
    print("构建的上下文:")
    print(SEPARATOR)
    print(context)
    print(SEPARATOR)
    summarize_context(context)
    print(f"   构建耗时：{elapsed:.1f}s")
    print(SEPARATOR)

    print(f"\n{SEPARATOR}")
    print("[4/4] 用构建好的上下文调用 LLM")
    print(SEPARATOR)
    llm = HelloAgentsLLM()
    started = time.time()
    answer = llm.invoke([{"role": "user", "content": context}])
    elapsed = time.time() - started
    print(answer)
    print(SEPARATOR)
    print(f"   LLM 回答耗时：{elapsed:.1f}s（model={llm.model}）")


if __name__ == "__main__":
    main()
