"""第九章实验的框架适配与数据准备辅助。

内容：
- Chapter9RAGTool：把 ContextBuilder 内部的 RAG 检索固定到本章的命名空间与集合，
  避免与第八章实验（default 命名空间 / rag_knowledge_base 集合）的数据混用。
- Chapter9TerminalTool：TerminalTool 的控制台输出解码容错（Windows 实测问题）。
- purge_user_memories：清理本实验用户的历史记忆，保证重复运行结果可复现。
- seed_memories / seed_knowledge_base：写入本章实验的记忆与知识库数据。
"""

from __future__ import annotations

import locale
import os
import subprocess
from typing import Any, Dict, List

from hello_agents.tools import MemoryTool, RAGTool, TerminalTool

from core.config import KNOWLEDGE_BASE_DIR

# 本章实验使用的用户 / 命名空间 / 集合，与第八章实验隔离
DEMO_USER_ID = "ch9_demo_user"
RAG_NAMESPACE = "chapter9"
RAG_COLLECTION = "chapter9_rag"

# 实验用记忆（与教程示例一致）
DEMO_MEMORIES: List[Dict[str, Any]] = [
    {
        "content": "用户正在开发数据分析工具，使用Python和Pandas",
        "memory_type": "semantic",
        "importance": 0.8,
    },
    {
        "content": "已完成CSV读取模块的开发",
        "memory_type": "episodic",
        "importance": 0.7,
    },
]

KNOWLEDGE_DOC = KNOWLEDGE_BASE_DIR / "pandas_memory_optimization.md"


class Chapter9RAGTool(RAGTool):
    """RAGTool 子类：为缺省 namespace 的调用补上本章命名空间。

    ContextBuilder._gather 内部调用 ``rag_tool.run({"action": "search", ...})``
    时不带 namespace，而 RAGTool._preprocess_parameters 会把缺省值填成 "default"，
    导致检索落到第八章的 default 命名空间。这里在 run() 里补上 self.rag_namespace。
    """

    def run(self, parameters: Dict[str, Any]) -> str:
        params = dict(parameters)
        if not params.get("namespace"):
            params["namespace"] = self.rag_namespace
        return super().run(params)


class Chapter9TerminalTool(TerminalTool):
    """TerminalTool 子类：控制台输出解码容错（Windows 实测问题）。

    0.2.8 的 TerminalTool._execute_command 以 ``text=True`` 捕获子进程输出并按
    UTF-8 严格解码；Windows cmd 的错误信息与中文路径是 GBK 字节，解码失败会让
    subprocess 的读取线程抛 UnicodeDecodeError，输出整体丢失、只剩返回码
    （实测教程命令 ``find . -type f -name '*.py' | head -n 20`` 返回
    "⚠️ 命令返回码: 255"）。这里改为捕获字节后按
    UTF-8 → 本地编码 → GBK 的顺序解码（均失败时 errors="replace"），
    保证命令输出（包括失败信息）始终可读。
    """

    @staticmethod
    def _decode_output(data: bytes) -> str:
        """按候选编码解码子进程输出（Windows cmd 输出为 GBK 字节）。"""
        candidates = []
        for encoding in ("utf-8", locale.getpreferredencoding(False), "gbk"):
            if encoding and encoding.lower() not in candidates:
                candidates.append(encoding.lower())
        for encoding in candidates:
            try:
                return data.decode(encoding)
            except (UnicodeDecodeError, LookupError):
                continue
        return data.decode("utf-8", errors="replace")

    def _execute_command(self, command: str) -> str:
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=str(self.current_dir),
                capture_output=True,
                timeout=self.timeout,
                env=os.environ.copy(),
            )

            # 合并标准输出和标准错误（字节捕获后按候选编码解码）
            output = self._decode_output(result.stdout)
            if result.stderr:
                output += f"\n[stderr]\n{self._decode_output(result.stderr)}"

            # 检查输出大小
            if len(output) > self.max_output_size:
                output = output[: self.max_output_size]
                output += f"\n\n⚠️ 输出被截断（超过 {self.max_output_size} 字节）"

            # 添加返回码信息
            if result.returncode != 0:
                output = f"⚠️ 命令返回码: {result.returncode}\n\n{output}"

            return output if output else "✅ 命令执行成功（无输出）"

        except subprocess.TimeoutExpired:
            return f"❌ 命令执行超时（超过 {self.timeout} 秒）"
        except Exception as exc:
            return f"❌ 命令执行失败: {exc}"


def purge_user_memories(memory_tool: MemoryTool, user_id: str) -> Dict[str, int]:
    """清理该用户的历史记忆，保证本实验重复运行可复现。

    - Qdrant（语义 + 情景向量）：按 user_id 过滤删除
    - SQLite（情景记忆权威库）：按 user_id 查询后逐条删除

    说明：框架自带的 remove / clear_all 只作用于进程内缓存或整库清空，
    无法按用户清理跨进程遗留的数据，因此这里直接操作底层存储。
    仅用于实验可复现性，不属于教程内容。
    """
    manager = memory_tool.memory_manager
    result = {"qdrant_vectors": 0, "episodic_docs": 0}

    semantic = manager.memory_types.get("semantic")
    if semantic is not None and getattr(semantic, "vector_store", None) is not None:
        try:
            from qdrant_client.http import models as qmodels

            store = semantic.vector_store
            flt = qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key="user_id", match=qmodels.MatchValue(value=user_id)
                    )
                ]
            )
            count = store.client.count(
                collection_name=store.collection_name, count_filter=flt, exact=True
            ).count
            if count:
                store.client.delete(
                    collection_name=store.collection_name,
                    points_selector=qmodels.FilterSelector(filter=flt),
                    wait=True,
                )
            result["qdrant_vectors"] = int(count)
        except Exception as exc:
            print(f"  ⚠️ 清理 Qdrant 记忆向量失败（已跳过）: {exc}")

    episodic = manager.memory_types.get("episodic")
    if episodic is not None and getattr(episodic, "doc_store", None) is not None:
        try:
            docs = episodic.doc_store.search_memories(
                user_id=user_id, memory_type="episodic", limit=10000
            )
            for doc in docs:
                episodic.doc_store.delete_memory(doc["memory_id"])
            result["episodic_docs"] = len(docs)
        except Exception as exc:
            print(f"  ⚠️ 清理情景记忆失败（已跳过）: {exc}")

    return result


def seed_memories(memory_tool: MemoryTool) -> List[str]:
    """写入实验记忆（语义 1 条 + 情景 1 条），返回工具输出。"""
    outputs = []
    for item in DEMO_MEMORIES:
        outputs.append(memory_tool.run({"action": "add", **item}))
    return outputs


def seed_knowledge_base(rag_tool: RAGTool) -> str:
    """把知识库文档写入本章 RAG 命名空间（按内容哈希 upsert，可重复运行）。"""
    return rag_tool.run(
        {
            "action": "add_document",
            "file_path": str(KNOWLEDGE_DOC),
            "namespace": RAG_NAMESPACE,
        }
    )
