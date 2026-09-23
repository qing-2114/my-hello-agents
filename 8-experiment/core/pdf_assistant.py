"""PDF 智能文档问答助手（第八章：记忆与检索）。

项目来源：https://hello-agents.datawhale.cc/

把 hello-agents==0.2.0 的 MemoryTool 与 RAGTool 组合成一个面向单份 PDF 的
学习助手：

- RAGTool：PDF 经 MarkItDown 解析 → 智能分块 → 向量化入 Qdrant → 检索 →
  LLM 生成带引用的答案；
- MemoryTool：工作记忆记录提问、情景记忆记录学习事件、语义记忆保存学习笔记，
  形成可回顾的学习轨迹。

适配说明（相对教程写法的差异，按 0.2.0 实际行为处理）：
1. execute(action, **kwargs) 返回带 ✅/❌ 前缀的格式化字符串，不是字典，
   因此用字符串前缀判断成功，而不是 result["success"]；
2. RAGTool._preprocess_parameters 会把未显式传入的 namespace 覆盖为
   "default"，所以每个 RAG 调用都显式携带 namespace=self.rag_namespace；
3. 0.2.0 的高级检索在 enable_advanced_search=True 时固定开启 MQE + HyDE，
   enable_mqe / enable_hyde 参数仅作前向兼容保留；
4. 语义记忆依赖 Neo4j 图数据库，框架在连不上时会直接抛异常。本类会捕获该
   异常并降级为「工作 + 情景」记忆（笔记降级写入情景记忆），保证 PDF 问答
   主链路可用；降级状态见 self.memory_degraded / self.memory_error；
5. 0.2.0 有三个实测缺陷会阻塞 PDF 入库（分块器死循环、Embedding 单请求超限、
   PDF 解析失败时把二进制流当文本写入），core/framework_fixes.py 在不改动
   site-packages 的前提下打补丁，本类初始化时自动应用。
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

EXPERIMENT_DIR = Path(__file__).resolve().parents[1]
if str(EXPERIMENT_DIR) not in sys.path:
    sys.path.insert(0, str(EXPERIMENT_DIR))

from hello_agents.memory import MemoryConfig
from hello_agents.tools import MemoryTool, RAGTool

from core.config import (
    KNOWLEDGE_BASE_DIR,
    MEMORY_DATA_DIR,
    REPORTS_DIR,
    load_project_environment,
)
from core.framework_fixes import apply_framework_fixes


class PDFLearningAssistant:
    """智能文档问答助手

    组合第八章的两个工具，围绕单份 PDF 提供「加载 → 提问 → 记笔记 → 回顾 →
    报告」的学习闭环。所有数据按 user_id 隔离：

    - 记忆：MemoryTool(user_id=...)，本地 SQLite + 向量库；
    - 知识库：RAGTool(rag_namespace=f"pdf_{user_id}")，同一 Qdrant 集合内按
      命名空间隔离。
    """

    def __init__(
        self,
        user_id: str = "default_user",
        knowledge_base_path: Optional[str] = None,
        memory_storage_path: Optional[str] = None,
        collection_name: str = "pdf_learning",
    ):
        """初始化学习助手

        Args:
            user_id: 用户ID，用于隔离不同用户的数据
            knowledge_base_path: RAG 知识库目录，默认 8-experiment/knowledge_base
            memory_storage_path: 记忆库目录，默认 8-experiment/memory_data
            collection_name: Qdrant 集合名，默认 pdf_learning
        """
        load_project_environment()  # 统一读取项目根目录 .env（幂等）
        apply_framework_fixes()  # 应用框架补丁，见 core/framework_fixes.py

        self.user_id = user_id
        self.session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # 初始化工具
        # 语义记忆依赖 Neo4j 图数据库；连不上时降级为「工作 + 情景」记忆，
        # 保证 PDF 问答主链路可用（笔记会降级写入情景记忆）。
        memory_config = MemoryConfig(
            storage_path=str(memory_storage_path or MEMORY_DATA_DIR)
        )
        self.memory_degraded = False
        self.memory_error: Optional[str] = None
        try:
            self.memory_tool = MemoryTool(
                user_id=user_id,
                memory_config=memory_config,
            )
        except Exception as exc:  # Neo4j 不可用时框架会在这里抛异常
            self.memory_degraded = True
            self.memory_error = str(exc)
            self.memory_tool = MemoryTool(
                user_id=user_id,
                memory_config=memory_config,
                memory_types=["working", "episodic"],
            )

        self.rag_namespace = f"pdf_{user_id}"
        self.rag_tool = RAGTool(
            knowledge_base_path=str(knowledge_base_path or KNOWLEDGE_BASE_DIR),
            collection_name=collection_name,
            rag_namespace=self.rag_namespace,
        )

        # 学习统计
        self.stats = {
            "session_start": datetime.now(),
            "documents_loaded": 0,
            "questions_asked": 0,
            "concepts_learned": 0,
        }

        # 当前加载的文档
        self.current_document = None

    # ------------------------------------------------------------------
    # 文档与问答
    # ------------------------------------------------------------------

    def load_document(self, pdf_path: str) -> Dict[str, Any]:
        """加载PDF文档到知识库

        Args:
            pdf_path: PDF文件路径

        Returns:
            Dict: 包含success和message的结果
        """
        if not os.path.exists(pdf_path):
            return {"success": False, "message": f"文件不存在: {pdf_path}"}

        start_time = time.time()

        # 【RAGTool】处理PDF: MarkItDown转换 → 智能分块 → 向量化
        result = self.rag_tool.execute(
            "add_document",
            file_path=pdf_path,
            namespace=self.rag_namespace,
            chunk_size=1000,
            chunk_overlap=200,
        )

        process_time = time.time() - start_time

        if result.startswith("✅"):
            self.current_document = os.path.basename(pdf_path)
            self.stats["documents_loaded"] += 1

            chunks = self._extract_int(result, r"分块数量:\s*(\d+)")
            memory_text = f"加载了文档《{self.current_document}》"
            if chunks is not None:
                memory_text += f"，共 {chunks} 个分块"

            # 【MemoryTool】记录到学习记忆
            self.memory_tool.execute(
                "add",
                content=memory_text,
                memory_type="episodic",
                importance=0.9,
                event_type="document_loaded",
                session_id=self.session_id,
            )

            return {
                "success": True,
                "message": f"加载成功！(耗时: {process_time:.1f}秒)",
                "document": self.current_document,
                "chunks": chunks,
                "details": result,
            }
        else:
            return {
                "success": False,
                "message": f"加载失败: {result}",
                "details": result,
            }

    def ask(self, question: str, use_advanced_search: bool = True) -> str:
        """向文档提问

        Args:
            question: 用户问题
            use_advanced_search: 是否使用高级检索（MQE + HyDE）

        Returns:
            str: 答案（RAGTool 已格式化为带引用来源的文本）
        """
        if not self.current_document:
            return "⚠️ 请先加载文档！"

        # 【MemoryTool】记录问题到工作记忆
        self.memory_tool.execute(
            "add",
            content=f"提问: {question}",
            memory_type="working",
            importance=0.6,
            session_id=self.session_id,
        )

        # 【RAGTool】使用高级检索获取答案
        answer = self.rag_tool.execute(
            "ask",
            question=question,
            namespace=self.rag_namespace,
            limit=5,
            enable_advanced_search=use_advanced_search,
            # 0.2.0 在高级检索内部固定开启 MQE + HyDE，这两个参数被忽略，
            # 保留仅为兼容后续版本
            enable_mqe=use_advanced_search,
            enable_hyde=use_advanced_search,
        )

        # 【MemoryTool】记录到情景记忆
        self.memory_tool.execute(
            "add",
            content=f"关于'{question}'的学习",
            memory_type="episodic",
            importance=0.7,
            event_type="qa_interaction",
            session_id=self.session_id,
        )

        self.stats["questions_asked"] += 1

        return answer

    # ------------------------------------------------------------------
    # 学习笔记与回顾
    # ------------------------------------------------------------------

    def add_note(self, content: str, concept: Optional[str] = None) -> str:
        """添加学习笔记（写入语义记忆）

        Returns:
            str: MemoryTool 的执行结果文本
        """
        # 语义记忆不可用时降级为情景记忆，避免笔记直接丢失
        memory_type = "episodic" if self.memory_degraded else "semantic"
        result = self.memory_tool.execute(
            "add",
            content=content,
            memory_type=memory_type,
            importance=0.8,
            concept=concept or "general",
            session_id=self.session_id,
        )
        if result.startswith("✅"):
            self.stats["concepts_learned"] += 1
        if self.memory_degraded:
            result = f"⚠️ 语义记忆（Neo4j）不可用，笔记已降级保存为情景记忆。\n{result}"
        return result

    def recall(self, query: str, limit: int = 5) -> str:
        """回顾学习历程

        Returns:
            str: 命中的记忆列表文本
        """
        return self.memory_tool.execute(
            "search",
            query=query,
            limit=limit,
        )

    # ------------------------------------------------------------------
    # 统计与报告
    # ------------------------------------------------------------------

    def get_stats(self) -> Dict[str, Any]:
        """获取学习统计"""
        duration = (datetime.now() - self.stats["session_start"]).total_seconds()
        return {
            "会话时长": f"{duration:.0f}秒",
            "加载文档": self.stats["documents_loaded"],
            "提问次数": self.stats["questions_asked"],
            "学习笔记": self.stats["concepts_learned"],
            "当前文档": self.current_document or "未加载",
            "记忆状态": "降级（Neo4j 不可用）" if self.memory_degraded else "正常",
        }

    def generate_report(self, save_to_file: bool = True) -> Dict[str, Any]:
        """生成学习报告

        Args:
            save_to_file: 是否把报告写入 8-experiment/reports/*.json

        Returns:
            Dict: 报告内容；save_to_file=True 时额外包含 report_file 路径
        """
        memory_summary = self.memory_tool.execute("summary", limit=10)
        rag_stats = self.rag_tool.execute("stats", namespace=self.rag_namespace)

        duration = (datetime.now() - self.stats["session_start"]).total_seconds()
        report = {
            "session_info": {
                "session_id": self.session_id,
                "user_id": self.user_id,
                "start_time": self.stats["session_start"].isoformat(),
                "duration_seconds": duration,
                "memory_degraded": self.memory_degraded,
                "memory_error": self.memory_error,
            },
            "learning_metrics": {
                "documents_loaded": self.stats["documents_loaded"],
                "questions_asked": self.stats["questions_asked"],
                "concepts_learned": self.stats["concepts_learned"],
            },
            "memory_summary": memory_summary,
            "rag_status": rag_stats,
        }

        if save_to_file:
            REPORTS_DIR.mkdir(parents=True, exist_ok=True)
            report_file = REPORTS_DIR / f"learning_report_{self.session_id}.json"
            with open(report_file, "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=2, default=str)
            report["report_file"] = str(report_file)

        return report

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_int(text: str, pattern: str) -> Optional[int]:
        """从工具返回文本中提取一个整数（如「分块数量: 123」）。"""
        match = re.search(pattern, text)
        return int(match.group(1)) if match else None
