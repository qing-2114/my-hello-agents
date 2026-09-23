"""第九章实验：ContextConfig 对比实验（观察 GSSC 各阶段的实际影响）。

对同一个查询、同一份数据，只改 ContextConfig，比较构建结果：

    A 教程配置        max_tokens=3000, min_relevance=0.2   -> 非系统包被相关性阈值过滤
    B 修正相关性阈值  max_tokens=3000, min_relevance=0.0   -> 候选包全部入选
    C 小预算          max_tokens=150,  min_relevance=0.0   -> 触发 Compress 截断
    D 关闭压缩        max_tokens=150,  min_relevance=0.0, enable_compression=False

用法（在 9-experiment 目录下）：
    # 离线桩数据：不访问网络，确定性复现 Select / Compress 行为
    F:\\my-hello-agent\\.conda\\python.exe -m demos.context_config_experiment --offline
    # 真实工具：写入记忆与知识库后构建（首次构建含 RAG 检索的 LLM 改写）
    F:\\my-hello-agent\\.conda\\python.exe -m demos.context_config_experiment
"""

from __future__ import annotations

import argparse
import contextlib
import io
import sys
import time
from pathlib import Path

EXPERIMENT_DIR = Path(__file__).resolve().parents[1]
if str(EXPERIMENT_DIR) not in sys.path:
    sys.path.insert(0, str(EXPERIMENT_DIR))

from hello_agents.context import ContextBuilder, ContextConfig
from hello_agents.context.builder import count_tokens

from demos.context_builder_demo import (
    CONVERSATION_HISTORY,
    SYSTEM_INSTRUCTIONS,
    USER_QUERY,
    create_tools,
    prepare_data,
    split_sections,
)

SEPARATOR = "=" * 80

CASES = [
    ("A 教程配置(min_relevance=0.2)", 3000, 0.2, True),
    ("B 修正阈值(min_relevance=0.0)", 3000, 0.0, True),
    ("C 小预算(max_tokens=150)", 150, 0.0, True),
    ("D 关闭压缩(max_tokens=150)", 150, 0.0, False),
]


class _StubMemory:
    """离线桩：返回固定记忆检索结果，不访问网络。"""

    def execute(self, action: str, **kwargs) -> str:
        if action == "search":
            return (
                "🔍 找到 1 条相关记忆:\n"
                "1. [语义记忆] 用户正在开发数据分析工具,使用Python和Pandas (重要性: 0.80)"
            )
        return ""


class _StubRAG:
    """离线桩：返回固定 RAG 检索结果，不访问网络。"""

    def run(self, parameters) -> str:
        return (
            "搜索结果：\n"
            "1. 文档: **pandas_memory_optimization.md** (相似度: 0.812)\n"
            "   先用 memory_usage(deep=True) 定位内存去向；dtype 降级与 category 转换收益最大。\n"
        )


class _CachedRAG:
    """缓存同一查询的 RAG 检索结果，4 组配置共用一次真实检索（含 MQE/HyDE 的 LLM 调用）。"""

    def __init__(self, rag_tool) -> None:
        self._rag_tool = rag_tool
        self._cache = {}

    def run(self, parameters):
        key = (parameters.get("action"), parameters.get("query"))
        if key not in self._cache:
            self._cache[key] = self._rag_tool.run(parameters)
        return self._cache[key]


def build_once(memory_tool, rag_tool, max_tokens, min_relevance, enable_compression):
    """按给定配置构建一次上下文，返回（上下文, 框架日志, 耗时）。"""
    config = ContextConfig(
        max_tokens=max_tokens,
        reserve_ratio=0.2,
        min_relevance=min_relevance,
        enable_compression=enable_compression,
    )
    builder = ContextBuilder(memory_tool=memory_tool, rag_tool=rag_tool, config=config)

    log_buffer = io.StringIO()
    started = time.time()
    with contextlib.redirect_stdout(log_buffer):
        context = builder.build(
            user_query=USER_QUERY,
            conversation_history=CONVERSATION_HISTORY,
            system_instructions=SYSTEM_INSTRUCTIONS,
        )
    elapsed = time.time() - started
    return context, log_buffer.getvalue(), elapsed


def sections_of(context: str) -> list[str]:
    return [block.split("]", 1)[0] + "]" for block in split_sections(context)]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ContextConfig 对比实验")
    parser.add_argument(
        "--offline",
        action="store_true",
        help="使用桩数据离线运行（不访问 Qdrant / Neo4j / LLM / Embedding）",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.offline:
        print(f"{SEPARATOR}\n离线模式：使用桩数据，不访问网络\n{SEPARATOR}")
        memory_tool, rag_tool = _StubMemory(), _StubRAG()
    else:
        print(f"{SEPARATOR}\n[1/2] 初始化真实工具并写入实验数据\n{SEPARATOR}")
        memory_tool, rag_tool = create_tools()
        prepare_data(memory_tool, rag_tool)
        rag_tool = _CachedRAG(rag_tool)
        print("   ℹ️ 4 组配置共用一次 RAG 检索结果（缓存），避免重复的 LLM 查询改写")

    results = []
    for name, max_tokens, min_relevance, enable_compression in CASES:
        context, log, elapsed = build_once(
            memory_tool, rag_tool, max_tokens, min_relevance, enable_compression
        )
        truncated = "执行截断" in log
        available = int(max_tokens * (1 - 0.2))
        results.append(
            {
                "name": name,
                "context": context,
                "sections": sections_of(context),
                "tokens": count_tokens(context),
                "available": available,
                "truncated": truncated,
                "elapsed": elapsed,
            }
        )

    print(f"\n{SEPARATOR}")
    print("[2/2] 对比结果")
    print(SEPARATOR)
    header = f"{'配置':<34}{'tokens':>8}{'预算':>8}  截断  分区"
    print(header)
    print("-" * len(header))
    for item in results:
        sections = ",".join(s[1:-1] for s in item["sections"])
        print(
            f"{item['name']:<34}{item['tokens']:>8}{item['available']:>8}  "
            f"{'是' if item['truncated'] else '否':<4}  {sections}"
        )

    for item in results:
        print(f"\n{SEPARATOR}")
        print(f"配置 {item['name']} 的完整上下文（{item['tokens']} tokens）")
        print(SEPARATOR)
        print(item["context"])
        print(SEPARATOR)
        if item["truncated"]:
            print("   ⚠️ 该配置触发了 Compress 阶段的按行截断（见 README「配置对比实验」）")


if __name__ == "__main__":
    main()
