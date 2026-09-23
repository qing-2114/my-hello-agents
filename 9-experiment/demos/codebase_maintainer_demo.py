"""第九章综合示例演示：代码库维护助手（CodebaseMaintainer）。

项目来源：https://hello-agents.datawhale.cc/

演示教程的「代码库维护助手」（长程智能体示例）的用法：

1. 初始化 CodebaseMaintainer（MemoryTool + NoteTool + TerminalTool + ContextBuilder）
2. explore 模式：TerminalTool 扫描代码库结构 → 注入 [Evidence]
3. analyze 模式：统计代码行数 + 查找 TODO/FIXME → 注入 [Evidence]
4. 手动记录一条 task_state 笔记（模拟维护任务）
5. plan 模式：加载任务列表 + 检索历史笔记 → 注入 [State]
6. 统计与报告：get_stats() / generate_report()

每轮打印：预处理包类型、检索到的笔记、上下文分区与 token 数、LLM 回答。

用法（在 9-experiment 目录下）：
    # 仅检查 .env、工具初始化与三条扫描命令，不发起对话
    F:\\my-hello-agent\\.conda\\python.exe -m demos.codebase_maintainer_demo --check
    # 完整实验：explore / analyze / plan 三轮交互 + 笔记 + 报告（真实 API）
    F:\\my-hello-agent\\.conda\\python.exe -m demos.codebase_maintainer_demo
    # 清空本实验的笔记工作区与该项目的记忆后重新开始
    F:\\my-hello-agent\\.conda\\python.exe -m demos.codebase_maintainer_demo --reset
    # 离线确定性检查：桩 LLM / 桩记忆 / 桩终端 + 临时笔记目录，不访问网络
    F:\\my-hello-agent\\.conda\\python.exe -m demos.codebase_maintainer_demo --offline
    # 复现教程阈值（min_relevance=0.2，观察结构包与笔记被相关性阈值过滤）
    F:\\my-hello-agent\\.conda\\python.exe -m demos.codebase_maintainer_demo --min-relevance 0.2
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

from core.chapter9_tools import purge_user_memories
from core.codebase_maintainer import CodebaseMaintainer, note_records
from core.config import NOTES_DIR, PROJECT_ROOT
from demos.context_builder_demo import split_sections

SEPARATOR = "=" * 80

PROJECT_NAME = "my_hello_agent"

# 三轮交互（教程的 explore / analyze / plan 用法）
EXPLORE_INPUT = "请探索代码库的整体结构"
ANALYZE_INPUT = "请分析代码质量"
PLAN_INPUT = "根据当前进度,规划下一步任务"

# 离线检查用的 blocker 查询（中文整句，用于对照内置 search 与关键词检索）
QUERY = "在重构业务逻辑层时,我遇到了依赖版本冲突的问题,该如何解决?"

# 复现教程阈值用的查询（不含自动笔记触发词，且不与任何笔记内容逐词相等）
THRESHOLD_QUERY = "请回顾一下当前状态"

# 演示中手动记录的维护任务
TASK_TITLE = "下一步:统一代码库扫描命令"
TASK_CONTENT = "把 Windows 与 POSIX 的探索命令统一到 core/scan_codebase.py,并补充离线测试。"

# describe_context 只统计框架的六个分区（包内容里以 [ 开头的行不算分区）
KNOWN_SECTIONS = (
    "[Role & Policies]",
    "[Task]",
    "[State]",
    "[Evidence]",
    "[Context]",
    "[Output]",
)


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
                "1. [语义记忆] 项目使用 Python + Conda 管理实验环境 (重要性: 0.80)"
            )
        return ""


class _StubTerminal:
    """离线桩终端：按命令返回固定输出（结构里故意混入 .conda 行，验证过滤）。"""

    def run(self, parameters) -> str:
        command = parameters.get("command", "")
        if "loc" in command or "wc -l" in command:
            return "files: 12\nlines: 1234"
        if "todo" in command or "grep" in command:
            return (
                "matches: 2\n"
                "1.3-experiment/agent.py:10: TODO: 补充错误处理\n"
                "demos/demo.py:3: FIXME: 输出格式"
            )
        return (
            "F:\\my-hello-agent\\9-experiment\\core\\config.py\n"
            "F:\\my-hello-agent\\9-experiment\\core\\codebase_maintainer.py\n"
            "F:\\my-hello-agent\\.conda\\Lib\\site-packages\\hello_agents\\__init__.py\n"
            "F:\\my-hello-agent\\.conda\\Lib\\site-packages\\hello_agents\\core\\llm.py\n"
        )


def check(label: str, ok: bool, detail: str = "") -> bool:
    print(f"   {'✅' if ok else '❌'} {label}" + (f"：{detail}" if detail else ""))
    return ok


def describe_context(context: str) -> str:
    """上下文的分区与 token 统计（只统计框架的六个分区）。"""
    sections = []
    for block in split_sections(context):
        name = block.split("]", 1)[0] + "]"
        if name in KNOWN_SECTIONS:
            sections.append(name)
    return f"{count_tokens(context)} tokens | 分区：{' '.join(sections)}"


def print_note_hits(maintainer: CodebaseMaintainer) -> None:
    """打印本轮检索到的笔记。"""
    if not maintainer.last_notes:
        print("   检索到笔记：0 条")
        return
    print(f"   检索到笔记：{len(maintainer.last_notes)} 条")
    for note in maintainer.last_notes:
        print(f"     • [{note.get('type')}] {note.get('title')} ({note['id']})")


def note_type_by_id(maintainer: CodebaseMaintainer, note_id: str) -> str:
    """按 ID 查询笔记类型（离线检查用）。"""
    for note in note_records(maintainer.note_tool):
        if note["id"] == note_id:
            return note.get("type", "")
    return ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="代码库维护助手（CodebaseMaintainer）演示")
    parser.add_argument(
        "--check",
        action="store_true",
        help="仅检查 .env、工具初始化与扫描命令，不发起对话 LLM 请求",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="离线确定性检查：桩 LLM/记忆/终端 + 临时笔记目录，不访问网络",
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
            "0.2.8 按空格分词计算相关性，中文查询下所有非系统包（含结构包与笔记包）"
            "相关性恒为 0，教程默认值 0.2 会把它们全部过滤；"
            "传入 0.2 可复现该现象，详见 README「实测发现」。"
        ),
    )
    parser.add_argument(
        "--codebase",
        default=str(PROJECT_ROOT),
        help="被维护的代码库目录（默认项目根目录）",
    )
    return parser.parse_args()


def run_offline(args: argparse.Namespace) -> bool:
    """离线确定性检查：验证「终端预处理 / 笔记 → ContextPacket → 上下文分区」链路。

    不需要网络与 API 额度，但项目根目录 .env 仍需存在（构造函数统一加载配置）。
    返回 True 表示全部检查通过。
    """
    print(f"{SEPARATOR}\n离线模式：桩 LLM / 桩记忆 / 桩终端 + 临时笔记目录\n{SEPARATOR}")

    checks: list[bool] = []
    with tempfile.TemporaryDirectory(prefix="ch9_codemaint_") as tmp:
        tmp_path = Path(tmp)
        notes_dir = tmp_path / "notes"
        maintainer = CodebaseMaintainer(
            PROJECT_NAME,
            codebase_path=tmp_path,
            llm=_StubLLM(),
            memory_tool=_StubMemory(),
            terminal_tool=_StubTerminal(),
            notes_dir=notes_dir,
            min_relevance=args.min_relevance,
        )

        print("\n[1/4] explore / auto 模式预处理")
        maintainer.run(EXPLORE_INPUT, mode="explore")
        checks.append(
            check(
                "explore 预处理包映射为 tool_result",
                maintainer.last_preprocess == ["tool_result"],
                f"预处理包：{maintainer.last_preprocess}",
            )
        )
        context = maintainer.last_context
        checks.append(
            check(
                "结构包进入 [Evidence] 且过滤 .conda 行",
                "[代码库结构]" in context
                and "[Evidence]" in context
                and "config.py" in context
                and ".conda" not in context,
                describe_context(context),
            )
        )
        maintainer.run("顺便看看项目里有什么", mode="auto")
        checks.append(
            check(
                "auto 模式同样预扫结构（教程语义）",
                maintainer.last_preprocess == ["tool_result"],
                f"预处理包：{maintainer.last_preprocess}",
            )
        )

        print("\n[2/4] analyze 模式预处理")
        maintainer.run(ANALYZE_INPUT, mode="analyze")
        context = maintainer.last_context
        checks.append(
            check(
                "analyze 预处理包含统计与 TODO",
                "[代码统计]" in context
                and "lines: 1234" in context
                and "[待办事项]" in context
                and "TODO" in context,
                describe_context(context),
            )
        )

        print("\n[3/4] 笔记链路：创建 → 检索 → 注入 [State]")
        maintainer.create_note(
            "依赖版本冲突阻塞重构",
            "在重构业务逻辑层时,依赖版本冲突导致构建失败",
            note_type="blocker",
            tags=[PROJECT_NAME, "dependency"],
        )
        maintainer.create_note(
            TASK_TITLE,
            TASK_CONTENT,
            note_type="task_state",
            tags=[PROJECT_NAME],
        )
        builtin = maintainer.note_tool.run(
            {"action": "search", "query": QUERY, "limit": 3}
        )
        checks.append(
            check(
                "框架内置 search（整串子串）未命中",
                "未找到" in builtin,
                "中文整句查询在 0.2.8 下恒不命中，见 README「笔记检索」",
            )
        )
        maintainer.run(QUERY, mode="plan")
        checks.append(
            check(
                "关键词检索命中 blocker 笔记（blocker 优先）",
                bool(maintainer.last_notes)
                and maintainer.last_notes[0]["type"] == "blocker",
                f"{[note['id'] for note in maintainer.last_notes]}",
            )
        )
        context = maintainer.last_context
        checks.append(
            check(
                "笔记进入 [State] 分区",
                "[State]" in context and "[笔记:" in context,
                describe_context(context),
            )
        )
        checks.append(
            check(
                "plan 预处理加载 task_state 任务列表",
                maintainer.last_preprocess == ["task_state"]
                and "[当前任务]" in context,
                f"预处理包：{maintainer.last_preprocess}",
            )
        )

        print("\n[4/4] 自动笔记、教程阈值与报告")
        checks.append(
            check(
                "自动笔记 blocker 分支（按用户输入分类）",
                maintainer.last_auto_note_id is not None
                and note_type_by_id(maintainer, maintainer.last_auto_note_id) == "blocker"
                and maintainer.stats["issues_found"] == 1,
                f"自动笔记 ID：{maintainer.last_auto_note_id}",
            )
        )
        maintainer.run(PLAN_INPUT, mode="plan")
        checks.append(
            check(
                "自动笔记 action 分支可达（教程的 elif 不可达）",
                maintainer.last_auto_note_id is not None
                and note_type_by_id(maintainer, maintainer.last_auto_note_id) == "action",
                f"自动笔记 ID：{maintainer.last_auto_note_id}",
            )
        )

        tutorial_maintainer = CodebaseMaintainer(
            PROJECT_NAME,
            codebase_path=tmp_path,
            llm=_StubLLM(),
            memory_tool=_StubMemory(),
            terminal_tool=_StubTerminal(),
            notes_dir=notes_dir,
            min_relevance=0.2,
        )
        tutorial_maintainer.run(THRESHOLD_QUERY, mode="plan")
        tutorial_context = tutorial_maintainer.last_context
        checks.append(
            check(
                "min_relevance=0.2 时预处理包与笔记被全部过滤",
                "[笔记:" not in tutorial_context
                and "[State]" not in tutorial_context
                and "[当前任务]" not in tutorial_context,
                describe_context(tutorial_context),
            )
        )

        report = maintainer.generate_report(
            save_to_file=True, report_dir=tmp_path / "reports"
        )
        checks.append(
            check(
                "报告生成（笔记数 / 命令数统计）",
                Path(report["report_file"]).is_file()
                and report["activity"]["notes_created"] >= 4
                and report["activity"]["commands_executed"] >= 4,
                f"activity={report['activity']}",
            )
        )
        checks.append(
            check(
                "对话历史更新（5 轮 × 2 条）",
                len(maintainer.conversation_history) == 10,
                f"历史消息数：{len(maintainer.conversation_history)}",
            )
        )

    passed = sum(1 for ok in checks if ok)
    print(f"\n{SEPARATOR}")
    print(f"离线检查：{passed}/{len(checks)} 通过")
    print(SEPARATOR)
    return passed == len(checks)


def reset_experiment(maintainer: CodebaseMaintainer) -> None:
    """清空本实验的笔记工作区与该项目用户的历史记忆。"""
    notes_workspace = Path(maintainer.notes_workspace).resolve()
    if notes_workspace.is_dir() and NOTES_DIR.resolve() in notes_workspace.parents:
        shutil.rmtree(notes_workspace)
        print(f"   🧹 已清空笔记工作区：{notes_workspace}")
    # 重新创建 NoteTool：工作区被删除后需要重建目录与空索引
    maintainer.notes_workspace.mkdir(parents=True, exist_ok=True)
    maintainer.note_tool = NoteTool(workspace=str(maintainer.notes_workspace))
    purged = purge_user_memories(maintainer.memory_tool, maintainer.memory_user_id)
    print(
        "   🧹 已清空记忆："
        f"Qdrant 向量 {purged['qdrant_vectors']} 条，"
        f"SQLite 情景记忆 {purged['episodic_docs']} 条"
    )


def show_round(maintainer: CodebaseMaintainer, label: str) -> None:
    """打印一轮交互的预处理包、笔记、上下文统计。"""
    print(f"   {label} 预处理包：{maintainer.last_preprocess or '（无）'}")
    print_note_hits(maintainer)
    print(f"   {label} 上下文：{describe_context(maintainer.last_context)}")


def main() -> None:
    args = parse_args()

    if args.offline:
        sys.exit(0 if run_offline(args) else 1)

    print(SEPARATOR)
    print("[1/6] 初始化代码库维护助手")
    print(SEPARATOR)
    maintainer = CodebaseMaintainer(
        project_name=PROJECT_NAME,
        codebase_path=args.codebase,
        min_relevance=args.min_relevance,
    )
    print(f"   ✅ LLM：{maintainer.llm.provider} / {maintainer.llm.model}")
    print(
        f"   ✅ 记忆工具：user_id={maintainer.memory_user_id}，"
        f"记忆类型={maintainer.memory_tool.memory_types}"
    )
    print(f"   ✅ 笔记工作区：{maintainer.notes_workspace}")
    print(f"   ✅ 终端工作区（代码库）：{maintainer.codebase_path}")
    print(f"   ✅ 会话ID：{maintainer.session_id}")

    if args.check:
        print("\n   扫描命令自检（不发起对话 LLM 请求）：")
        for label, command in (
            ("结构", maintainer._explore_command()),
            ("统计", maintainer._loc_command()),
            ("TODO", maintainer._todo_command()),
        ):
            output = maintainer.terminal_tool.run({"command": command})
            if label == "结构":
                output = maintainer._summarize_structure(output)
            first = output.splitlines()[0] if output.splitlines() else "（无输出）"
            print(f"   ✅ {label}：{command}")
            print(f"      {first}")
        print("\n配置检查通过")
        return

    if args.reset:
        print(f"\n{SEPARATOR}")
        print("[2/6] 重置实验数据（笔记工作区 + 该项目记忆）")
        print(SEPARATOR)
        reset_experiment(maintainer)
    else:
        print(f"\n{SEPARATOR}")
        print("[2/6] 实验数据（当前笔记）")
        print(SEPARATOR)
        print(f"   笔记工作区现有笔记：{maintainer.note_workspace_state() or '（空）'}")

    print(f"\n{SEPARATOR}")
    print("[3/6] explore 模式：探索代码库结构")
    print(SEPARATOR)
    print(f"   用户：{EXPLORE_INPUT}")
    started = time.time()
    answer = maintainer.run(EXPLORE_INPUT, mode="explore")
    elapsed = time.time() - started
    show_round(maintainer, "explore")
    print(
        "   结构包进入上下文："
        f"{'是' if '[代码库结构]' in maintainer.last_context else '否'}"
    )
    print(f"\n   助手（{elapsed:.1f}s）：\n{answer}")

    print(f"\n{SEPARATOR}")
    print("[4/6] analyze 模式：分析代码质量")
    print(SEPARATOR)
    print(f"   用户：{ANALYZE_INPUT}")
    started = time.time()
    answer = maintainer.run(ANALYZE_INPUT, mode="analyze")
    elapsed = time.time() - started
    show_round(maintainer, "analyze")
    print(
        "   统计包进入上下文："
        f"{'是' if '[代码统计]' in maintainer.last_context else '否'}"
    )
    print(f"\n   助手（{elapsed:.1f}s）：\n{answer}")

    print(f"\n{SEPARATOR}")
    print("[5/6] plan 模式：记录维护任务后规划下一步")
    print(SEPARATOR)
    print("   记录 task_state 笔记：")
    print(f"   {maintainer.create_note(TASK_TITLE, TASK_CONTENT, note_type='task_state', tags=[PROJECT_NAME]).replace(chr(10), ' / ')}")
    print(f"   用户：{PLAN_INPUT}")
    started = time.time()
    answer = maintainer.run(PLAN_INPUT, mode="plan")
    elapsed = time.time() - started
    show_round(maintainer, "plan")
    print(
        "   任务列表进入上下文："
        f"{'是' if '[当前任务]' in maintainer.last_context else '否'}"
    )
    print(f"\n   助手（{elapsed:.1f}s）：\n{answer}")

    print(f"\n{SEPARATOR}")
    print("[6/6] 会话统计与报告")
    print(SEPARATOR)
    print(maintainer.notes_summary())
    print(f"   按类型统计：{maintainer.note_workspace_state()}")
    report = maintainer.generate_report(save_to_file=True)
    print(f"   报告文件：{report.get('report_file')}")
    print(f"   activity：{report['activity']}")


if __name__ == "__main__":
    main()
