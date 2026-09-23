"""第九章 §9.4.4 示例的可运行实现：长期项目助手（NoteTool + ContextBuilder）。

项目来源：https://hello-agents.datawhale.cc/

教程 §9.4.4「与 ContextBuilder 的深度集成」给出 ProjectAssistant：
把 NoteTool 的结构化笔记检索出来转成 ContextPacket，注入 GSSC 上下文
（Gather-Select-Structure-Compress），让 Agent 跨轮次、跨进程保持项目连续性。

本文件是教程示例在 hello-agents==0.2.8 上的可运行版本。相对教程写法的适配点
（每条都在 9-experiment/README.md「长期项目助手」一节有对应说明）：

1. NoteTool.run() 返回的是格式化字符串，不是 list[dict]：拿不到 note_id /
   content / updated_at。这里改用 note_tool.notes_index + 笔记文件解析结果
   构造结构化记录（键是 id 而不是 note_id）。
2. 内置 search 动作是「整串子串匹配」，中文整句查询几乎不可能命中；检索改为
   关键词打分（英文按词、中文按 2 字滑窗），blocker 笔记仍然优先。
3. ContextBuilder.build() 的额外包参数名是 additional_packets（教程写
   custom_packets，会直接 TypeError）。
4. ContextPacket.metadata["type"] 必须落在框架认识的取值里（instructions /
   task_state / related_memory / knowledge_base / retrieval / tool_result /
   history），否则 Structure 阶段会静默丢弃该包——教程用 "note"，笔记根本进不了
   最终上下文。这里 blocker/action 映射为 task_state（→ [State]），其余映射为
   retrieval（→ [Evidence]）。
5. ContextPacket.relevance_score 会被 _select 用空格分词重算，教程里的 0.75
   是死值；token_count 传 0 时由 __post_init__ 用 tiktoken 精确计算，
   不需要 len(content)//4 估算。
6. HelloAgentsLLM.invoke() 接收 messages 列表，不是裸字符串。

与教程示例一致的部分：笔记按关键词分类（问题/阻塞 → blocker，计划/下一步 →
action，其余 conclusion）、笔记内容带标题前缀、对话历史截断到最近 10 条、
note_as_action=True 时把本次交互落成笔记。
"""

from __future__ import annotations

import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

EXPERIMENT_DIR = Path(__file__).resolve().parents[1]
if str(EXPERIMENT_DIR) not in sys.path:
    sys.path.insert(0, str(EXPERIMENT_DIR))

from hello_agents import HelloAgentsLLM, SimpleAgent
from hello_agents.context import ContextBuilder, ContextConfig, ContextPacket
from hello_agents.core.message import Message
from hello_agents.memory import MemoryConfig
from hello_agents.tools import MemoryTool, NoteTool

from core.chapter9_tools import RAG_COLLECTION, RAG_NAMESPACE, Chapter9RAGTool
from core.config import (
    KNOWLEDGE_BASE_DIR,
    MEMORY_DATA_DIR,
    NOTES_DIR,
    load_project_environment,
)

# 笔记类型 → ContextPacket.metadata["type"]
# 框架 _structure 只认识 instructions / task_state / related_memory /
# knowledge_base / retrieval / tool_result / history，未列出的类型会被静默丢弃。
PACKET_TYPE_BY_NOTE_TYPE = {
    "blocker": "task_state",     # → [State] 关键进展与未决问题
    "action": "task_state",
    "task_state": "task_state",
    "conclusion": "retrieval",   # → [Evidence] 事实与引用
    "reference": "retrieval",
    "general": "retrieval",
}

_WORD_RE = re.compile(r"[A-Za-z0-9_]+")
_CJK_RUN_RE = re.compile(r"[\u4e00-\u9fff]+")


def query_keywords(query: str) -> List[str]:
    """把查询切成字面匹配用的关键词（英文按词、中文按 2 字滑窗）。"""
    keywords = {word.lower() for word in _WORD_RE.findall(query)}
    for run in _CJK_RUN_RE.findall(query):
        if len(run) == 1:
            keywords.add(run)
        else:
            keywords.update(run[i:i + 2] for i in range(len(run) - 1))
    return sorted(keywords)


def score_note(note: Dict[str, Any], keywords: List[str]) -> int:
    """关键词打分：标题/标签命中 2 分，正文命中 1 分。"""
    title = str(note.get("title", "")).lower()
    content = str(note.get("content", "")).lower()
    tags = [str(tag).lower() for tag in note.get("tags", [])]
    score = 0
    for keyword in keywords:
        if keyword in title or any(keyword in tag for tag in tags):
            score += 2
        elif keyword in content:
            score += 1
    return score


class ProjectAssistant(SimpleAgent):
    """长期项目助手：NoteTool 笔记 + ContextBuilder 上下文 + LLM 回答。

    数据隔离（相对教程示例的调整，避免与第八章实验互相干扰）：

    - 笔记：9-experiment/notes/<project_name>/（教程用 CWD 下的 ./<project>_notes）
    - 记忆：user_id = ch9_<project_name>（教程直接用 project_name）
    - RAG：复用本章命名空间 chapter9 / 集合 chapter9_rag（教程另建 ./<project>_kb）
    """

    def __init__(
        self,
        name: str,
        project_name: str,
        *,
        llm: Optional[Any] = None,
        memory_tool: Optional[Any] = None,
        rag_tool: Optional[Any] = None,
        note_tool: Optional[NoteTool] = None,
        notes_dir: Optional[Path] = None,
        memory_user_id: Optional[str] = None,
        rag_namespace: str = RAG_NAMESPACE,
        collection_name: str = RAG_COLLECTION,
        knowledge_base_path: Optional[Path] = None,
        min_relevance: float = 0.0,
        max_tokens: int = 4000,
        **kwargs: Any,
    ):
        """初始化长期项目助手。

        llm / memory_tool / rag_tool / note_tool 是测试注入点：不传时按教程
        构造真实工具（MemoryTool + Chapter9RAGTool + NoteTool），传了则直接使用
        （离线演示用桩对象替代，见 demos/project_assistant_demo.py --offline）。

        min_relevance 默认 0.0：0.2.8 按空格分词算相关性，中文查询下所有非系统包
        相关性恒为 0，教程默认值 0.2 会把笔记、记忆、RAG 全部过滤掉，
        详见 README「实测发现」。
        """
        load_project_environment()  # 统一读取项目根目录 .env（幂等）

        super().__init__(name=name, llm=llm or HelloAgentsLLM(), **kwargs)

        self.project_name = project_name
        self.memory_user_id = memory_user_id or f"ch9_{project_name}"

        # 工具：记忆（语义 + 情景）、RAG（本章命名空间）、笔记（Markdown 工作区）
        self.memory_tool = memory_tool or MemoryTool(
            user_id=self.memory_user_id,
            memory_config=MemoryConfig(storage_path=str(MEMORY_DATA_DIR)),
        )
        if rag_tool is not None:
            self.rag_tool = rag_tool
        else:
            self.rag_tool = Chapter9RAGTool(
                knowledge_base_path=str(knowledge_base_path or KNOWLEDGE_BASE_DIR),
                collection_name=collection_name,
                rag_namespace=rag_namespace,
            )
            if not getattr(self.rag_tool, "initialized", False):
                raise RuntimeError(
                    "RAG 工具初始化失败："
                    f"{getattr(self.rag_tool, 'init_error', '未知错误')}"
                )
        self.notes_workspace = Path(notes_dir or (NOTES_DIR / project_name))
        self.note_tool = note_tool or NoteTool(workspace=str(self.notes_workspace))

        # 上下文构建器（GSSC 流水线）
        self.context_builder = ContextBuilder(
            memory_tool=self.memory_tool,
            rag_tool=self.rag_tool,
            config=ContextConfig(
                max_tokens=max_tokens,
                reserve_ratio=0.2,
                min_relevance=min_relevance,
                enable_compression=True,
            ),
        )

        self.conversation_history: List[Message] = []

        # 最近一次运行的中间结果（供演示与验证读取，不参与对话）
        self.last_context: str = ""
        self.last_notes: List[Dict[str, Any]] = []
        self.last_note_result: str = ""
        self.last_saved_note_id: Optional[str] = None

    # ------------------------------------------------------------------
    # 主流程
    # ------------------------------------------------------------------

    def run(self, user_input: str, note_as_action: bool = False) -> str:
        """运行助手：检索笔记 → 构建上下文 → 调用 LLM →（可选）落笔记。

        Args:
            user_input: 用户输入
            note_as_action: True 时把本次交互保存为笔记（供后续轮次检索）

        Returns:
            str: LLM 回答
        """
        # 1. 检索相关笔记（blocker 优先 + 关键词命中）
        relevant_notes = self._retrieve_relevant_notes(user_input)
        self.last_notes = relevant_notes

        # 2. 笔记 → ContextPacket
        note_packets = self._notes_to_packets(relevant_notes)

        # 3. 构建优化的上下文（GSSC）
        context = self.context_builder.build(
            user_query=user_input,
            conversation_history=self.conversation_history,
            system_instructions=self._build_system_instructions(),
            additional_packets=note_packets,
        )
        self.last_context = context

        # 4. 调用 LLM（invoke 接收 messages 列表）
        response = self.llm.invoke([{"role": "user", "content": context}])

        # 5. 需要时把交互记录为笔记
        if note_as_action:
            self.last_note_result = self._save_as_note(user_input, response)

        # 6. 更新对话历史
        self._update_history(user_input, response)

        return response

    # ------------------------------------------------------------------
    # 笔记检索与转换
    # ------------------------------------------------------------------

    def builtin_note_search(self, query: str, limit: int = 3) -> str:
        """教程写法：直接调用 NoteTool 的 search 动作（整串子串匹配）。

        保留此入口是为了对照：中文整句查询在 0.2.8 下返回「未找到匹配」，
        而 _retrieve_relevant_notes 的关键词打分能命中（见 README「笔记检索」）。
        """
        return self.note_tool.run({"action": "search", "query": query, "limit": limit})

    def _retrieve_relevant_notes(self, query: str, limit: int = 3) -> List[Dict[str, Any]]:
        """检索相关笔记：blocker 笔记优先，其余按关键词得分排序。

        教程写法是 note_tool.run({"action": "list"/"search"}) 后把返回值当
        list[dict] 合并，在 0.2.8 上会直接报错（返回的是字符串）；这里改成
        读笔记索引与文件，语义与教程一致。
        """
        try:
            records = self._note_records()

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

    def _note_records(self) -> List[Dict[str, Any]]:
        """读取笔记索引与笔记文件，返回结构化记录（id/title/type/tags/updated_at/content）。

        注意：NoteTool 的索引在构造时加载一次，本进程运行期间其他进程新写的笔记
        不会自动出现在索引里（重启助手即可看到，跨进程连续性验证见 README）。
        """
        records: List[Dict[str, Any]] = []
        for entry in self.note_tool.notes_index.get("notes", []):
            note_path = self.note_tool._get_note_path(entry["id"])
            if not note_path.exists():
                continue
            try:
                note = self.note_tool._markdown_to_note(
                    note_path.read_text(encoding="utf-8")
                )
            except Exception as exc:
                print(f"[WARNING] 解析笔记失败 {entry['id']}: {exc}")
                continue
            note.setdefault("id", entry["id"])
            note.setdefault("title", entry.get("title", ""))
            note.setdefault("type", entry.get("type", "general"))
            records.append(note)
        return records

    def _notes_to_packets(self, notes: List[Dict[str, Any]]) -> List[ContextPacket]:
        """把笔记转换为上下文包。

        - metadata["type"] 用框架认识的值，否则 Structure 阶段静默丢弃；
        - token_count 留 0，由 ContextPacket.__post_init__ 用 tiktoken 计算；
        - relevance_score 留 0.0，_select 会用空格分词重算（写死值无效）。
        """
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
                        "type": PACKET_TYPE_BY_NOTE_TYPE.get(note.get("type"), "retrieval"),
                        "note_type": note.get("type", "general"),
                        "note_id": note["id"],
                    },
                )
            )
        return packets

    # ------------------------------------------------------------------
    # 笔记写入与历史
    # ------------------------------------------------------------------

    def _save_as_note(self, user_input: str, response: str) -> str:
        """将交互保存为笔记，返回 NoteTool 的输出文本。"""
        if "问题" in user_input or "阻塞" in user_input:
            note_type = "blocker"
        elif "计划" in user_input or "下一步" in user_input:
            note_type = "action"
        else:
            note_type = "conclusion"

        title = user_input[:30] + ("…" if len(user_input) > 30 else "")
        try:
            result = self.note_tool.run(
                {
                    "action": "create",
                    "title": title,
                    "content": f"## 问题\n{user_input}\n\n## 分析\n{response}",
                    "note_type": note_type,
                    "tags": [self.project_name, "auto_generated"],
                }
            )
            match = re.search(r"ID: (note_\S+)", result)
            self.last_saved_note_id = match.group(1) if match else None
            return result
        except Exception as exc:
            self.last_saved_note_id = None
            return f"❌ 保存笔记失败: {exc}"

    def _build_system_instructions(self) -> str:
        """构建系统指令（教程原文）。"""
        return f"""你是 {self.project_name} 项目的长期助手。

你的职责:
1. 基于历史笔记提供连贯的建议
2. 追踪项目进展和待解决问题
3. 在回答时引用相关的历史笔记
4. 提供具体、可操作的下一步建议

注意:
- 优先关注标记为 blocker 的问题
- 在建议中说明依据来源(笔记、记忆或知识库)
- 保持对项目整体进度的认识"""

    def _update_history(self, user_input: str, response: str) -> None:
        """更新对话历史（保留最近 10 条）。"""
        self.conversation_history.append(
            Message(content=user_input, role="user", timestamp=datetime.now())
        )
        self.conversation_history.append(
            Message(content=response, role="assistant", timestamp=datetime.now())
        )
        if len(self.conversation_history) > 10:
            self.conversation_history = self.conversation_history[-10:]

    # ------------------------------------------------------------------
    # 状态查询（演示用）
    # ------------------------------------------------------------------

    def note_workspace_state(self) -> Dict[str, int]:
        """按类型统计笔记数量。"""
        counts: Dict[str, int] = {}
        for entry in self.note_tool.notes_index.get("notes", []):
            note_type = entry.get("type", "general")
            counts[note_type] = counts.get(note_type, 0) + 1
        return counts

    def notes_summary(self) -> str:
        """教程用法：note_tool.run({"action": "summary"})。"""
        return self.note_tool.run({"action": "summary"})
