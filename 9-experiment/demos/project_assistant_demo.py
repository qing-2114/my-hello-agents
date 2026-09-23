"""第九章 §9.4.4 示例演示：长期项目助手（ProjectAssistant）。

项目来源：https://hello-agents.datawhale.cc/

演示教程 §9.4.4「与 ContextBuilder 的深度集成」的用法：

1. 初始化 ProjectAssistant（MemoryTool + Chapter9RAGTool + NoteTool + ContextBuilder）
2. 第一次交互：汇报项目状态，note_as_action=True 把交互落成笔记（action 类型）
3. 第二次交互：提出依赖冲突问题——笔记被检索、转成 ContextPacket 注入 [State]，
   验证「跨轮次/跨进程的项目连续性」
4. 笔记摘要 + 工作区统计

每轮打印：检索到的笔记、上下文分区与 token 数、上下文是否包含笔记、LLM 回答。

用法（在 9-experiment 目录下）：
    # 仅检查 .env、工具初始化与笔记工作区，不发起对话
    F:\\my-hello-agent\\.conda\\python.exe -m demos.project_assistant_demo --check
    # 完整实验：写入记忆/知识库 -> 两轮交互 -> 笔记摘要（真实 API）
    F:\\my-hello-agent\\.conda\\python.exe -m demos.project_assistant_demo
    # 清空本实验的笔记工作区与记忆后重新开始
    F:\\my-hello-agent\\.conda\\python.exe -m demos.project_assistant_demo --reset
    # 离线确定性检查：桩 LLM / 桩记忆 / 桩 RAG + 临时笔记目录，不访问网络
    F:\\my-hello-agent\\.conda\\python.exe -m demos.project_assistant_demo --offline
    # 复现教程阈值（min_relevance=0.2，观察笔记包被相关性阈值过滤）
    F:\\my-hello-agent\\.conda\\python.exe -m demos.project_assistant_demo --min-relevance 0.2
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
import time
from pathlib import Path

EXPERIMENT_DIR = Path(__file__).resolve().parents[1]
if str(EXPERIMENT_DIR) not in sys.path:
    sys.path.insert(0, str(EXPERIMENT_DIR))

from hello_agents.context.builder import count_tokens
from hello_agents.tools import NoteTool

from core.chapter9_tools import (
    RAG_COLLECTION,
    RAG_NAMESPACE,
    purge_user_memories,
    seed_knowledge_base,
    seed_memories,
)
from core.config import NOTES_DIR
from core.project_assistant import ProjectAssistant
from demos.context_builder_demo import split_sections

SEPARATOR = "=" * 80

PROJECT_NAME = "data_pipeline_refactoring"

# 教程 §9.4.4 的两轮交互
FIRST_INPUT = "我们已经完成了数据模型层的重构,测试覆盖率达到85%。下一步计划重构业务逻辑层。"
SECOND_INPUT = "在重构业务逻辑层时,我遇到了依赖版本冲突的问题,该如何解决?"


class _StubLLM:
    """离线桩 LLM：不访问网络，把收到的上下文摘要回显出来。"""

    provider = "offline"
    model = "stub"

    def invoke(self, messages, **kwargs) -> str:
        context = messages[-1]["content"]
        sections = [block.split("]", 1)[0] + "]" for block in split_sections(context)]
        return (
            f"（离线桩回答）收到 {count_tokens(context)} tokens 的上下文，"
            f"分区：{', '.join(sections)}"
        )


class _StubMemory:
    """离线桩记忆：返回固定检索结果。"""

    def execute(self, action: str, **kwargs) -> str:
        if action == "search":
            return (
                "🔍 找到 1 条相关记忆:\n"
                "1. [语义记忆] 项目使用 Python + Pandas 处理数据管道 (重要性: 0.80)"
            )
        return ""


class _StubRAG:
    """离线桩 RAG：返回固定检索结果。"""

    def run(self, parameters) -> str:
        return (
            "搜索结果：\n"
            "1. 文档: **pandas_memory_optimization.md** (相似度: 0.810)\n"
            "   dtype 降级与 category 转换收益最大。"
        )


def describe_context(context: str) -> str:
    """上下文的分区与 token 统计。"""
    sections = [block.split("]", 1)[0] + "]" for block in split_sections(context)]
    return f"{count_tokens(context)} tokens | 分区：{' '.join(sections)}"


def print_note_hits(assistant: ProjectAssistant) -> None:
    """打印本轮检索到的笔记。"""
    if not assistant.last_notes:
        print("   检索到笔记：0 条")
        return
    print(f"   检索到笔记：{len(assistant.last_notes)} 条")
    for note in assistant.last_notes:
        print(f"     • [{note.get('type')}] {note.get('title')} ({note['id']})")


def show_round(assistant: ProjectAssistant, label: str) -> None:
    """打印一轮交互的上下文与回答。"""
    context = assistant.last_context
    print(f"   {label} 上下文：{describe_context(context)}")
    print(f"   {label} 上下文包含笔记：{'是' if '[笔记:' in context else '否'}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="长期项目助手（ProjectAssistant）演示")
    parser.add_argument(
        "--check",
        action="store_true",
        help="仅检查 .env、工具初始化与笔记工作区，不发起对话 LLM 请求",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="离线确定性检查：桩 LLM/记忆/RAG + 临时笔记目录，不访问网络",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help=f"运行前清空本实验的笔记工作区（{NOTES_DIR}）与该项目的记忆",
    )
    parser.add_argument(
        "--min-relevance",
        type=float,
        default=0.0,
        help=(
            "Select 阶段的最小相关性阈值（默认 0.0）。"
            "0.2.8 按空格分词计算相关性，中文查询下所有非系统包（含笔记包）"
            "相关性恒为 0，教程默认值 0.2 会把它们全部过滤；"
            "传入 0.2 可复现该现象，详见 README「实测发现」。"
        ),
    )
    return parser.parse_args()


def run_offline(args: argparse.Namespace) -> bool:
    """离线确定性检查：验证「笔记 -> ContextPacket -> 上下文分区」链路。

    不需要网络与 API 额度，但项目根目录 .env 仍需存在（构造函数统一加载配置）。
    返回 True 表示全部检查通过。
    """
    print(f"{SEPARATOR}\n离线模式：桩 LLM / 桩记忆 / 桩 RAG + 临时笔记目录\n{SEPARATOR}")

    checks: list[bool] = []
    with tempfile.TemporaryDirectory(prefix="ch9_notes_") as tmp:
        notes_dir = Path(tmp)
        assistant = ProjectAssistant(
            name="项目助手(离线)",
            project_name=PROJECT_NAME,
            llm=_StubLLM(),
            memory_tool=_StubMemory(),
            rag_tool=_StubRAG(),
            notes_dir=notes_dir,
            min_relevance=args.min_relevance,
        )

        print("\n[1/3] 第一次交互（note_as_action=True）")
        assistant.run(FIRST_INPUT, note_as_action=True)
        state = assistant.note_workspace_state()
        checks.append(
            check(
                "交互已落成笔记",
                sum(state.values()) == 1 and state.get("action") == 1,
                f"工作区统计 {state}，笔记 ID {assistant.last_saved_note_id}",
            )
        )
        checks.append(
            check(
                "第一次交互无历史笔记可检索",
                assistant.last_notes == [],
                "首轮没有笔记，属于预期",
            )
        )

        print("\n[2/3] 第二次交互（应检索到上一轮的笔记）")
        assistant.run(SECOND_INPUT)
        builtin = assistant.builtin_note_search(SECOND_INPUT)
        checks.append(
            check(
                "框架内置 search（整串子串）未命中",
                "未找到" in builtin,
                "中文整句查询在 0.2.8 下恒不命中，见 README「笔记检索」",
            )
        )
        checks.append(
            check(
                "关键词检索命中上一轮笔记",
                len(assistant.last_notes) == 1,
                f"{[note['id'] for note in assistant.last_notes]}",
            )
        )
        context = assistant.last_context
        checks.append(
            check(
                "笔记进入 [State] 分区",
                "[State]" in context and "[笔记:" in context,
                describe_context(context),
            )
        )
        checks.append(
            check(
                "记忆与 RAG 桩数据进入 [Evidence]",
                "[Evidence]" in context,
                "上下文完整包含六个分区" if "[Context]" in context else "缺少 [Context]",
            )
        )

        print("\n[3/3] 复现教程阈值（min_relevance=0.2）")
        tutorial_assistant = ProjectAssistant(
            name="项目助手(教程阈值)",
            project_name=PROJECT_NAME,
            llm=_StubLLM(),
            memory_tool=_StubMemory(),
            rag_tool=_StubRAG(),
            notes_dir=notes_dir,
            min_relevance=0.2,
        )
        tutorial_assistant.run(SECOND_INPUT)
        tutorial_context = tutorial_assistant.last_context
        checks.append(
            check(
                "min_relevance=0.2 时笔记与检索结果被全部过滤",
                "[笔记:" not in tutorial_context and "[State]" not in tutorial_context,
                describe_context(tutorial_context),
            )
        )

    passed = sum(1 for ok in checks if ok)
    print(f"\n{SEPARATOR}")
    print(f"离线检查：{passed}/{len(checks)} 通过")
    print(SEPARATOR)
    return passed == len(checks)


def check(label: str, ok: bool, detail: str = "") -> bool:
    print(f"   {'✅' if ok else '❌'} {label}" + (f"：{detail}" if detail else ""))
    return ok


def reset_experiment(assistant: ProjectAssistant) -> None:
    """清空本实验的笔记工作区与该项目用户的历史记忆。"""
    notes_workspace = Path(assistant.notes_workspace).resolve()
    if notes_workspace.is_dir() and NOTES_DIR.resolve() in notes_workspace.parents:
        shutil.rmtree(notes_workspace)
        print(f"   🧹 已清空笔记工作区：{notes_workspace}")
    # 重新创建 NoteTool：工作区被删除后需要重建目录与空索引
    assistant.notes_workspace.mkdir(parents=True, exist_ok=True)
    assistant.note_tool = NoteTool(workspace=str(assistant.notes_workspace))
    purged = purge_user_memories(assistant.memory_tool, assistant.memory_user_id)
    print(
        "   🧹 已清空记忆："
        f"Qdrant 向量 {purged['qdrant_vectors']} 条，"
        f"SQLite 情景记忆 {purged['episodic_docs']} 条"
    )


def main() -> None:
    args = parse_args()

    if args.offline:
        sys.exit(0 if run_offline(args) else 1)

    print(SEPARATOR)
    print("[1/5] 初始化长期项目助手")
    print(SEPARATOR)
    assistant = ProjectAssistant(
        name="项目助手",
        project_name=PROJECT_NAME,
        min_relevance=args.min_relevance,
    )
    print(f"   ✅ LLM：{assistant.llm.provider} / {assistant.llm.model}")
    print(
        f"   ✅ 记忆工具：user_id={assistant.memory_user_id}，"
        f"记忆类型={assistant.memory_tool.memory_types}"
    )
    print(
        f"   ✅ RAG 工具：namespace={assistant.rag_tool.rag_namespace}，"
        f"collection={assistant.rag_tool.collection_name}"
    )
    print(f"   ✅ 笔记工作区：{assistant.notes_workspace}")

    if args.check:
        print("\n配置检查通过（--check 模式不发起对话 LLM 请求）")
        return

    if args.reset:
        print(f"\n{SEPARATOR}")
        print("[2/5] 准备实验数据（重置 + 写入记忆 / 知识库）")
        print(SEPARATOR)
        reset_experiment(assistant)
    else:
        print(f"\n{SEPARATOR}")
        print("[2/5] 准备实验数据（写入记忆 / 知识库）")
        print(SEPARATOR)
    for line in seed_memories(assistant.memory_tool):
        print(f"   {line}")
    print(f"   {seed_knowledge_base(assistant.rag_tool)}")
    print(f"   笔记工作区现有笔记：{assistant.note_workspace_state() or '（空）'}")

    print(f"\n{SEPARATOR}")
    print("[3/5] 第一次交互：汇报项目状态（note_as_action=True）")
    print(SEPARATOR)
    print(f"   用户：{FIRST_INPUT}")
    started = time.time()
    answer = assistant.run(FIRST_INPUT, note_as_action=True)
    elapsed = time.time() - started
    print_note_hits(assistant)
    show_round(assistant, "第一次")
    print("   落笔记：" + assistant.last_note_result.replace("\n", " / "))
    print(f"\n   助手（{elapsed:.1f}s）：\n{answer}")

    print(f"\n{SEPARATOR}")
    print("[4/5] 第二次交互：依赖冲突问题（应引用上一轮笔记）")
    print(SEPARATOR)
    print(f"   用户：{SECOND_INPUT}")
    builtin = assistant.builtin_note_search(SECOND_INPUT)
    print(f"   对照：框架内置 search 返回「{builtin.splitlines()[0]}」")
    started = time.time()
    answer = assistant.run(SECOND_INPUT)
    elapsed = time.time() - started
    print_note_hits(assistant)
    show_round(assistant, "第二次")
    print(f"\n   助手（{elapsed:.1f}s）：\n{answer}")

    print(f"\n{SEPARATOR}")
    print("[5/5] 笔记摘要")
    print(SEPARATOR)
    print(assistant.notes_summary())
    print(f"   工作区：{assistant.notes_workspace}")
    print(f"   按类型统计：{assistant.note_workspace_state()}")


if __name__ == "__main__":
    main()
