"""第八章：PDF 智能文档问答助手 CLI 演示（MemoryTool + RAGTool）。

项目来源：https://hello-agents.datawhale.cc/

用于命令行验证「加载 PDF → 提问 → 记笔记 → 回顾 → 报告」全链路。
配置统一读取项目根目录 .env。

用法（在 8-experiment 目录下执行）：

    # 仅检查 .env 与工具初始化（不加载文档、不提问）
    python -m demos.pdf_learning_assistant_demo --check

    # 加载 PDF 并提问（--question 可多次传入）
    python -m demos.pdf_learning_assistant_demo --pdf "C:/Users/asus/Downloads/Happy-LLM-0727.pdf" --question "这本书主要讲什么？"

    # 记一条笔记、按关键词回顾、生成学习报告
    python -m demos.pdf_learning_assistant_demo --note "注意力机制是核心概念之一" --recall "注意力" --report
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

EXPERIMENT_DIR = Path(__file__).resolve().parents[1]
if str(EXPERIMENT_DIR) not in sys.path:
    sys.path.insert(0, str(EXPERIMENT_DIR))

from core.pdf_assistant import PDFLearningAssistant


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PDF 智能文档问答助手命令行演示")
    parser.add_argument(
        "--check",
        action="store_true",
        help="仅检查 .env 与工具初始化，不加载文档、不提问",
    )
    parser.add_argument(
        "--user-id",
        default="default_user",
        help="用户ID（数据隔离），默认 default_user",
    )
    parser.add_argument("--pdf", help="要加载的 PDF 路径")
    parser.add_argument(
        "--question",
        action="append",
        default=[],
        help="向文档提问（可多次传入）",
    )
    parser.add_argument(
        "--note",
        action="append",
        default=[],
        help="添加学习笔记（可多次传入）",
    )
    parser.add_argument("--recall", help="按关键词回顾学习记忆")
    parser.add_argument("--report", action="store_true", help="生成并保存学习报告")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    assistant = PDFLearningAssistant(user_id=args.user_id)

    if args.check:
        llm = getattr(assistant.rag_tool, "llm", None)
        rag_ok = getattr(assistant.rag_tool, "initialized", False)
        print("配置检查通过：")
        print(
            "  provider="
            f"{getattr(llm, 'provider', 'unknown')}, "
            f"model={getattr(llm, 'model', 'unknown')}"
        )
        print(f"  rag_namespace={assistant.rag_namespace}")
        print(f"  rag_tool_initialized={rag_ok}")
        print(f"  memory_degraded={assistant.memory_degraded}")
        if not rag_ok:
            print(f"  init_error={getattr(assistant.rag_tool, 'init_error', '未知错误')}")
        if assistant.memory_degraded:
            print(f"  memory_error={assistant.memory_error}")
        return

    if assistant.memory_degraded:
        print(f"⚠️ 语义记忆（Neo4j）不可用，已降级：{assistant.memory_error}")

    if args.pdf:
        result = assistant.load_document(args.pdf)
        print(f"[加载] {result['message']}")
        if result.get("details"):
            print(result["details"])

    for question in args.question:
        print(f"\n[提问] {question}")
        print(assistant.ask(question))

    for note in args.note:
        print(f"\n[笔记] {assistant.add_note(note)}")

    if args.recall:
        print(f"\n[回顾] {args.recall}")
        print(assistant.recall(args.recall))

    print("\n[统计]")
    for key, value in assistant.get_stats().items():
        print(f"  {key}: {value}")

    if args.report:
        report = assistant.generate_report(save_to_file=True)
        print("\n[报告]")
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
