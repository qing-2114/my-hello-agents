"""第九章综合示例的可运行实现：代码库维护助手（CodebaseMaintainer）。

项目来源：https://hello-agents.datawhale.cc/

教程的「代码库维护助手」（长程智能体示例）把 ContextBuilder + NoteTool +
TerminalTool + MemoryTool 组合成跨会话的代码库维护任务管理。本文件是它在
hello-agents==0.2.8 上的可运行版本，适配点（每条在 9-experiment/README.md
「代码库维护助手」一节有对应说明）：

1. ``build(..., additional_packets=...)``：教程写 ``custom_packets``，0.2.8 会
   直接 TypeError。
2. ``HelloAgentsLLM.invoke()`` 接收 messages 列表，不是裸字符串。
3. ``NoteTool.run()`` 返回格式化字符串，不是 ``list[dict]``：教程的笔记合并
   会被自身 except 吞掉（检索恒为空），plan 模式 ``note['title']`` 直接崩溃；
   这里读 ``notes_index`` + 解析笔记文件，检索复用 project_assistant 的关键词打分。
4. ``ContextPacket.metadata["type"]`` 必须落在框架认识的取值里，否则 Structure
   阶段静默丢弃：笔记 → task_state / retrieval，终端结果 → tool_result，
   任务列表 → task_state（教程的 note / code_structure / code_analysis /
   task_plan 全部进不了上下文）。
5. ``relevance_score`` 写死无效（``_select`` 会用空格分词重算）；``token_count``
   留 0 由 tiktoken 精确计算（教程的 ``len(content)//4`` 对中文低估约 4 倍）。
6. ``min_relevance`` 默认 0.0：中文查询下教程默认值 0.2 会把非系统包全部过滤。
7. TerminalTool 命令按平台生成：Windows 用 ``dir /s /b *.py`` 与本章的
   ``core/scan_codebase.py``（PATH python，仅标准库），POSIX 保留教程的
   find/grep/wc；配合 ``Chapter9TerminalTool`` 解决 Windows 输出解码问题。
8. 自动笔记改为按用户输入分类：教程按回复关键词触发且 if/elif 顺序使计划分支
   不可达（中文回复几乎必然命中「问题」）。
9. 会话报告写到 ``9-experiment/reports/``（教程写到 CWD）。

与教程示例一致的部分：模式化预处理（explore/analyze/plan/auto）、
blocker 优先的笔记检索、笔记内容带标题前缀、会话统计与报告、便捷方法
（explore / analyze / plan_next_steps / execute_command / create_note）。
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from hello_agents import HelloAgentsLLM
from hello_agents.context import ContextBuilder, ContextConfig, ContextPacket
from hello_agents.core.message import Message
from hello_agents.memory import MemoryConfig
from hello_agents.tools import MemoryTool, NoteTool

from core.chapter9_tools import Chapter9TerminalTool
from core.config import MEMORY_DATA_DIR, NOTES_DIR, REPORTS_DIR, load_project_environment
from core.project_assistant import PACKET_TYPE_BY_NOTE_TYPE, query_keywords, score_note

# 结构扫描时过滤的目录（与 core/scan_codebase.py 保持一致）
EXCLUDED_PATH_PARTS = (
    ".conda",
    ".git",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    ".zcode",
)

# Windows 下供 TerminalTool 调用的标准库扫描脚本
SCAN_SCRIPT = Path(__file__).resolve().parent / "scan_codebase.py"

# 自动笔记触发词（按用户输入分类；教程按回复关键词分类，见模块 docstring 第 8 条）
BLOCKER_KEYWORDS = ("问题", "bug", "错误", "阻塞", "失败")
ACTION_KEYWORDS = ("计划", "下一步", "任务", "todo")


def note_records(note_tool: NoteTool) -> List[Dict[str, Any]]:
    """读取笔记索引与笔记文件，返回结构化记录（id/title/type/tags/updated_at/content）。

    与 ProjectAssistant 的实现相同（教程把 ``note_tool.run(...)`` 的返回值当
    ``list[dict]`` 用，在 0.2.8 上拿不到任何字段）。注意：NoteTool 的索引在
    构造时加载一次，本进程运行期间其他进程新写的笔记不会自动出现
    （重启助手即可看到）。
    """
    records: List[Dict[str, Any]] = []
    for entry in note_tool.notes_index.get("notes", []):
        note_path = note_tool._get_note_path(entry["id"])
        if not note_path.exists():
            continue
        try:
            note = note_tool._markdown_to_note(note_path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"[WARNING] 解析笔记失败 {entry['id']}: {exc}")
            continue
        note.setdefault("id", entry["id"])
        note.setdefault("title", entry.get("title", ""))
        note.setdefault("type", entry.get("type", "general"))
        records.append(note)
    return records


class CodebaseMaintainer:
    """代码库维护助手：TerminalTool 探索 + NoteTool 笔记 + ContextBuilder 上下文。

    数据隔离（相对教程示例的调整）：
    - 笔记：9-experiment/notes/<project_name>/
    - 记忆：user_id = ch9_<project_name>
    - 报告：9-experiment/reports/maintainer_report_<session_id>.json
    """

    def __init__(
        self,
        project_name: str,
        codebase_path: str,
        *,
        llm: Optional[Any] = None,
        memory_tool: Optional[Any] = None,
        note_tool: Optional[NoteTool] = None,
        terminal_tool: Optional[Any] = None,
        notes_dir: Optional[Path] = None,
        memory_user_id: Optional[str] = None,
        min_relevance: float = 0.0,
        max_tokens: int = 4000,
    ):
        """初始化代码库维护助手。

        llm / memory_tool / note_tool / terminal_tool 是测试注入点：不传时按
        教程构造真实工具（HelloAgentsLLM + MemoryTool + NoteTool +
        Chapter9TerminalTool），传了则直接使用（离线演示用桩对象替代）。

        min_relevance 默认 0.0：0.2.8 按空格分词算相关性，中文查询下所有非系统包
        相关性恒为 0，教程默认值 0.2 会把终端结果、笔记、记忆全部过滤掉，
        详见 README「实测发现」。
        """
        load_project_environment()  # 统一读取项目根目录 .env（幂等）

        self.project_name = project_name
        self.codebase_path = str(Path(codebase_path).resolve())
        self.session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.memory_user_id = memory_user_id or f"ch9_{project_name}"

        # 工具：LLM、记忆（语义 + 情景）、笔记（Markdown 工作区）、终端（解码容错）
        self.llm = llm or HelloAgentsLLM()
        self.memory_tool = memory_tool or MemoryTool(
            user_id=self.memory_user_id,
            memory_config=MemoryConfig(storage_path=str(MEMORY_DATA_DIR)),
        )
        self.notes_workspace = Path(notes_dir or (NOTES_DIR / project_name))
        self.note_tool = note_tool or NoteTool(workspace=str(self.notes_workspace))
        self.terminal_tool = terminal_tool or Chapter9TerminalTool(
            workspace=self.codebase_path, timeout=60
        )

        # 上下文构建器（GSSC 流水线；本案例不使用 RAG）
        self.context_builder = ContextBuilder(
            memory_tool=self.memory_tool,
            rag_tool=None,
            config=ContextConfig(
                max_tokens=max_tokens,
                reserve_ratio=0.15,
                min_relevance=min_relevance,
                enable_compression=True,
            ),
        )

        # 对话历史与统计（教程字段）
        self.conversation_history: List[Message] = []
        self.stats = {
            "session_start": datetime.now(),
            "commands_executed": 0,
            "notes_created": 0,
            "issues_found": 0,
        }

        # 最近一次运行的中间结果（供演示与验证读取，不参与对话）
        self.last_context: str = ""
        self.last_notes: List[Dict[str, Any]] = []
        self.last_preprocess: List[str] = []
        self.last_auto_note_id: Optional[str] = None
        self.last_auto_note_result: str = ""
        self.last_saved_note_id: Optional[str] = None

    # ------------------------------------------------------------------
    # 主流程
    # ------------------------------------------------------------------

    def run(self, user_input: str, mode: str = "auto") -> str:
        """运行助手：模式预处理 → 检索笔记 → 构建上下文 → 调用 LLM → 后处理。

        Args:
            user_input: 用户输入
            mode: 运行模式
                - "auto": 自动决策（预处理同 explore）
                - "explore": 侧重代码探索
                - "analyze": 侧重问题分析
                - "plan": 侧重任务规划

        Returns:
            str: 助手的回答
        """
        # 1. 按模式预处理（TerminalTool 探索 / 笔记任务列表）
        pre_packets = self._preprocess_by_mode(user_input, mode)
        self.last_preprocess = [
            packet.metadata.get("type", "") for packet in pre_packets
        ]

        # 2. 检索相关笔记（blocker 优先 + 关键词命中）
        relevant_notes = self._retrieve_relevant_notes(user_input)
        self.last_notes = relevant_notes

        # 3. 笔记 → ContextPacket
        note_packets = self._notes_to_packets(relevant_notes)

        # 4. 构建优化的上下文（GSSC；额外包参数名是 additional_packets）
        context = self.context_builder.build(
            user_query=user_input,
            conversation_history=self.conversation_history,
            system_instructions=self._build_system_instructions(mode),
            additional_packets=pre_packets + note_packets,
        )
        self.last_context = context

        # 5. 调用 LLM（invoke 接收 messages 列表）
        response = self.llm.invoke([{"role": "user", "content": context}])

        # 6. 后处理：按用户输入自动落笔记
        self._postprocess_response(user_input, response)

        # 7. 更新对话历史
        self._update_history(user_input, response)

        return response

    # ------------------------------------------------------------------
    # 模式化预处理
    # ------------------------------------------------------------------

    def _preprocess_by_mode(self, user_input: str, mode: str) -> List[ContextPacket]:
        """根据模式执行预处理，收集相关信息（教程语义，命令按平台生成）。"""
        packets: List[ContextPacket] = []

        if mode in ("explore", "auto"):
            structure = self.terminal_tool.run({"command": self._explore_command()})
            self.stats["commands_executed"] += 1
            packets.append(
                ContextPacket(
                    content=f"[代码库结构]\n{self._summarize_structure(structure)}",
                    timestamp=datetime.now(),
                    metadata={
                        "type": "tool_result",  # → [Evidence]
                        "source": "terminal",
                        "origin": "code_structure",
                    },
                )
            )

        if mode == "analyze":
            loc = self.terminal_tool.run({"command": self._loc_command()})
            todos = self.terminal_tool.run({"command": self._todo_command()})
            self.stats["commands_executed"] += 2
            packets.append(
                ContextPacket(
                    content=(
                        f"[代码统计]\n{self._truncate(loc, 500)}"
                        f"\n\n[待办事项]\n{self._truncate(todos, 1500)}"
                    ),
                    timestamp=datetime.now(),
                    metadata={
                        "type": "tool_result",  # → [Evidence]
                        "source": "terminal",
                        "origin": "code_analysis",
                    },
                )
            )

        if mode == "plan":
            # 教程用 note_tool.run({"action": "list", ...}) 并当 list[dict] 迭代，
            # 0.2.8 返回字符串，会直接 TypeError；这里读结构化记录。
            task_notes = [
                note for note in note_records(self.note_tool)
                if note.get("type") == "task_state"
            ]
            task_notes.sort(key=lambda note: note.get("updated_at", ""), reverse=True)
            task_notes = task_notes[:3]
            if task_notes:
                content = "\n".join(
                    f"- {note['title']} ({note['id']})" for note in task_notes
                )
                packets.append(
                    ContextPacket(
                        content=f"[当前任务]\n{content}",
                        timestamp=datetime.now(),
                        metadata={
                            "type": "task_state",  # → [State]
                            "source": "notes",
                            "origin": "task_plan",
                        },
                    )
                )

        return packets

    def _explore_command(self) -> str:
        """代码结构扫描命令（按平台生成；教程的 find 组合在 cmd 下不可用）。"""
        if os.name == "nt":
            return "dir /s /b *.py"
        return "find . -type f -name '*.py'"

    def _loc_command(self) -> str:
        """代码行数统计命令。"""
        if os.name == "nt":
            return f"python {SCAN_SCRIPT.as_posix()} loc"
        return "find . -name '*.py' -exec wc -l {} + | tail -n 1"

    def _todo_command(self) -> str:
        """TODO/FIXME 扫描命令。"""
        if os.name == "nt":
            return f"python {SCAN_SCRIPT.as_posix()} todo --limit 10"
        return "grep -rn 'TODO\\|FIXME' --include='*.py' | head -n 10"

    def _summarize_structure(self, raw: str, limit: int = 20) -> str:
        """过滤被排除目录并截断结构列表，保持包内容可读。"""
        py_lines = [
            line.strip() for line in raw.splitlines() if line.strip().endswith(".py")
        ]
        kept = [
            line for line in py_lines
            if not any(part in line for part in EXCLUDED_PATH_PARTS)
        ]
        if not kept:
            return self._truncate(raw, 1000)
        shown = kept[:limit]
        return (
            f"python files: {len(kept)}（显示前 {len(shown)} 个）\n"
            + "\n".join(shown)
        )

    @staticmethod
    def _truncate(text: str, max_chars: int) -> str:
        if len(text) <= max_chars:
            return text
        return text[:max_chars] + f"...（已截断，共 {len(text)} 字符）"

    # ------------------------------------------------------------------
    # 笔记检索与转换
    # ------------------------------------------------------------------

    def _retrieve_relevant_notes(self, query: str, limit: int = 3) -> List[Dict[str, Any]]:
        """检索相关笔记：blocker 笔记优先，其余按关键词得分排序。

        教程写法（note_tool.run 的字符串结果当 list[dict] 合并）在 0.2.8 上会
        抛 AttributeError 并被自身 except 吞掉，检索恒为空；这里改为读结构化
        记录 + 关键词打分，语义与教程一致。
        """
        try:
            records = note_records(self.note_tool)

            blockers = [note for note in records if note.get("type") == "blocker"]
            blockers.sort(key=lambda note: note.get("updated_at", ""), reverse=True)
            blockers = blockers[:2]

            keywords = query_keywords(query)
            scored = []
            for note in records:
                score = score_note(note, keywords)
                if score > 0:
                    scored.append((score, note))
            scored.sort(
                key=lambda item: (item[0], item[1].get("updated_at", "")), reverse=True
            )
            matched = [note for _, note in scored][:limit]

            # 合并去重，blocker 在前（与教程一致）
            merged: Dict[str, Dict[str, Any]] = {}
            for note in blockers + matched:
                merged.setdefault(note["id"], note)
            return list(merged.values())[:limit]

        except Exception as exc:
            print(f"[WARNING] 笔记检索失败: {exc}")
            return []

    def _notes_to_packets(self, notes: List[Dict[str, Any]]) -> List[ContextPacket]:
        """把笔记转换为上下文包（metadata type 用框架认识的值，见模块 docstring）。"""
        packets: List[ContextPacket] = []
        for note in notes:
            content = f"[笔记:{note['title']}]\n{note['content']}"
            try:
                timestamp = datetime.fromisoformat(note["updated_at"])
            except (KeyError, ValueError):
                timestamp = datetime.now()
            packets.append(
                ContextPacket(
                    content=content,
                    timestamp=timestamp,
                    metadata={
                        "type": PACKET_TYPE_BY_NOTE_TYPE.get(
                            note.get("type"), "retrieval"
                        ),
                        "note_type": note.get("type", "general"),
                        "note_id": note["id"],
                        "origin": "note",
                    },
                )
            )
        return packets

    def _build_system_instructions(self, mode: str) -> str:
        """构建系统指令（教程原文 + 模式说明）。"""
        base_instructions = f"""你是 {self.project_name} 项目的代码库维护助手。

你的核心能力:
1. 使用 TerminalTool 探索代码库
2. 使用 NoteTool 记录发现和任务
3. 基于历史笔记提供连贯的建议

当前会话ID: {self.session_id}
"""

        mode_specific = {
            "explore": """
当前模式: 探索代码库

你应该:
- 主动使用 terminal 命令了解代码结构
- 识别关键模块和文件
- 记录项目架构到笔记
""",
            "analyze": """
当前模式: 分析代码质量

你应该:
- 查找代码问题(重复、复杂度、TODO等)
- 评估代码质量
- 将发现的问题记录为 blocker 或 action 笔记
""",
            "plan": """
当前模式: 任务规划

你应该:
- 回顾历史笔记和任务
- 制定下一步行动计划
- 更新任务状态笔记
""",
            "auto": """
当前模式: 自动决策

你应该:
- 根据用户需求灵活选择策略
- 在需要时使用工具
- 保持回答的专业性和实用性
""",
        }

        return base_instructions + mode_specific.get(mode, mode_specific["auto"])

    # ------------------------------------------------------------------
    # 后处理与笔记写入
    # ------------------------------------------------------------------

    def _postprocess_response(self, user_input: str, response: str) -> None:
        """按用户输入分类并自动落笔记。

        教程按回复关键词触发（中文回复几乎必然命中「问题」），且 if/elif 顺序
        让计划分支不可达；这里改为按用户输入分类，两个分支都可达。
        """
        text = user_input.lower()
        if any(keyword in text for keyword in BLOCKER_KEYWORDS):
            note_type = "blocker"
            title = f"发现问题: {user_input[:30]}{'…' if len(user_input) > 30 else ''}"
            content = f"## 用户输入\n{user_input}\n\n## 问题分析\n{response}"
            self.stats["issues_found"] += 1
        elif any(keyword in text for keyword in ACTION_KEYWORDS):
            note_type = "action"
            title = f"任务规划: {user_input[:30]}{'…' if len(user_input) > 30 else ''}"
            content = f"## 讨论\n{user_input}\n\n## 行动计划\n{response}"
        else:
            return

        try:
            result = self.note_tool.run(
                {
                    "action": "create",
                    "title": title,
                    "content": content,
                    "note_type": note_type,
                    "tags": [self.project_name, "auto_detected", self.session_id],
                }
            )
            self.stats["notes_created"] += 1
            match = re.search(r"ID: (note_\S+)", result)
            self.last_auto_note_id = match.group(1) if match else None
            self.last_auto_note_result = result
        except Exception as exc:
            self.last_auto_note_id = None
            self.last_auto_note_result = f"❌ 自动笔记失败: {exc}"

    def create_note(
        self,
        title: str,
        content: str,
        note_type: str = "general",
        tags: Optional[List[str]] = None,
    ) -> str:
        """创建笔记（教程便捷方法；记录最近一次创建的笔记 ID）。"""
        result = self.note_tool.run(
            {
                "action": "create",
                "title": title,
                "content": content,
                "note_type": note_type,
                "tags": tags or [self.project_name],
            }
        )
        self.stats["notes_created"] += 1
        match = re.search(r"ID: (note_\S+)", result)
        self.last_saved_note_id = match.group(1) if match else None
        return result

    def _update_history(self, user_input: str, response: str) -> None:
        """更新对话历史（教程保留最近 20 条）。"""
        self.conversation_history.append(
            Message(content=user_input, role="user", timestamp=datetime.now())
        )
        self.conversation_history.append(
            Message(content=response, role="assistant", timestamp=datetime.now())
        )
        if len(self.conversation_history) > 20:
            self.conversation_history = self.conversation_history[-20:]

    # ------------------------------------------------------------------
    # 便捷方法与状态查询
    # ------------------------------------------------------------------

    def explore(self, target: str = ".") -> str:
        """探索代码库。"""
        return self.run(f"请探索 {target} 的代码结构", mode="explore")

    def analyze(self, focus: str = "") -> str:
        """分析代码质量。"""
        query = "请分析代码质量" + (f",重点关注{focus}" if focus else "")
        return self.run(query, mode="analyze")

    def plan_next_steps(self) -> str:
        """规划下一步任务。"""
        return self.run("根据当前进度,规划下一步任务", mode="plan")

    def execute_command(self, command: str) -> str:
        """执行终端命令（TerminalTool 白名单内）。"""
        result = self.terminal_tool.run({"command": command})
        self.stats["commands_executed"] += 1
        return result

    def note_workspace_state(self) -> Dict[str, int]:
        """按类型统计笔记数量。"""
        counts: Dict[str, int] = {}
        for entry in self.note_tool.notes_index.get("notes", []):
            note_type = entry.get("type", "general")
            counts[note_type] = counts.get(note_type, 0) + 1
        return counts

    def notes_summary(self) -> str:
        """笔记摘要（NoteTool 的 summary 动作，返回格式化字符串）。"""
        return self.note_tool.run({"action": "summary"})

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息（教程字段 + 代码库路径）。"""
        duration = (datetime.now() - self.stats["session_start"]).total_seconds()
        try:
            note_summary = self.note_tool.run({"action": "summary"})
        except Exception:
            note_summary = ""

        return {
            "session_info": {
                "session_id": self.session_id,
                "project": self.project_name,
                "codebase": self.codebase_path,
                "duration_seconds": duration,
            },
            "activity": {
                "commands_executed": self.stats["commands_executed"],
                "notes_created": self.stats["notes_created"],
                "issues_found": self.stats["issues_found"],
            },
            "notes": note_summary,
        }

    def generate_report(
        self, save_to_file: bool = True, report_dir: Optional[Path] = None
    ) -> Dict[str, Any]:
        """生成会话报告（教程写到 CWD；这里默认写到 9-experiment/reports/）。"""
        report = self.get_stats()

        if save_to_file:
            target_dir = Path(report_dir or REPORTS_DIR)
            target_dir.mkdir(parents=True, exist_ok=True)
            report_file = target_dir / f"maintainer_report_{self.session_id}.json"
            with open(report_file, "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=2, default=str)
            report["report_file"] = str(report_file)

        return report
