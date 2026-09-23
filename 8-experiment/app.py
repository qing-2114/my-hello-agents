"""PDF 智能文档问答助手 · Gradio Web 界面。

项目来源：https://hello-agents.datawhale.cc/

在浏览器中提供「上传 PDF → 问答 → 记笔记 → 回顾 → 报告」的完整交互。
每个浏览器会话对应一个独立的 PDFLearningAssistant（由 gr.State 持有），
首次操作时懒加载创建；「用户ID」输入框用于隔离不同用户的数据。

兼容 Gradio 4.44.x（hello-agents 的 evaluation extra 依赖）与 Gradio 6.x：
4.x 需要显式给 Chatbot 指定 messages 格式，且有两个上游缺陷在启动时打补丁
（matplotlib 后端管理器、api_info 的 bool schema 解析）。

用法（在 8-experiment 目录下执行）：

    F:/my-hello-agent/.conda/python.exe app.py

然后打开 http://127.0.0.1:7860
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

EXPERIMENT_DIR = Path(__file__).resolve().parent
if str(EXPERIMENT_DIR) not in sys.path:
    sys.path.insert(0, str(EXPERIMENT_DIR))

import gradio as gr

from core.pdf_assistant import PDFLearningAssistant

# ---------------------------------------------------------------------------
# 会话与助手管理
# ---------------------------------------------------------------------------


def _resolve_assistant(
    state: Optional[PDFLearningAssistant], user_id: str
) -> PDFLearningAssistant:
    """按浏览器会话懒加载助手实例；用户ID变化时重建（相当于切换账号）。"""
    uid = (user_id or "").strip() or "default_user"
    if state is None or getattr(state, "user_id", None) != uid:
        state = PDFLearningAssistant(user_id=uid)
    return state


def _stats_markdown(assistant: PDFLearningAssistant) -> str:
    stats = assistant.get_stats()
    return "\n".join(f"- **{key}**：{value}" for key, value in stats.items())


def _degraded_notice(assistant: PDFLearningAssistant) -> str:
    """Neo4j 不可用时的降级提示（语义记忆降级为情景记忆）。"""
    if getattr(assistant, "memory_degraded", False):
        return "\n\n⚠️ 语义记忆（Neo4j）当前不可用，笔记将降级保存为情景记忆。"
    return ""


# ---------------------------------------------------------------------------
# Gradio 版本兼容
# ---------------------------------------------------------------------------


def _patch_gradio_matplotlib_manager() -> None:
    """规避 Gradio 的 MatplotlibBackendMananger 缺陷（4.x / 6.x 均存在）。

    Gradio 每次请求都会用该上下文管理器把 matplotlib 后端切到 agg 再切回，
    但 __exit__ 直接读取 self._original_backend：一旦 __enter__ 里的
    import / get_backend 失败并被静默跳过（工作线程里偶发），__exit__ 就会抛
    AttributeError —— 请求本身已执行成功，前端却显示「错误」。这里替换为
    容错版本（后端切换只影响 LaTeX 渲染，与本应用功能无关）。
    """
    try:
        from gradio import utils as gradio_utils
    except Exception:
        return

    manager = getattr(gradio_utils, "MatplotlibBackendMananger", None)
    if manager is None or getattr(manager, "_tolerant_patch", False):
        return

    def _safe_enter(self):
        try:
            import matplotlib

            self._original_backend = matplotlib.get_backend()
            matplotlib.use("agg")
        except Exception:
            self._original_backend = None

    def _safe_exit(self, exc_type, exc_val, exc_tb):
        backend = getattr(self, "_original_backend", None)
        if not backend:
            return
        try:
            import matplotlib

            matplotlib.use(backend)
        except Exception:
            pass

    manager.__enter__ = _safe_enter
    manager.__exit__ = _safe_exit
    manager._tolerant_patch = True


def _patch_gradio_api_info() -> None:
    """规避 gradio_client 的 JSON Schema 解析缺陷（4.44.x）。

    Chatbot 消息模型的 metadata 字段会生成 `additionalProperties: true`（bool
    形式的 schema），gradio_client 1.3.0 的解析器遇到 bool 会抛 TypeError /
    APIInfoParseError，导致 / 路由的 api_info 生成失败、launch 的 localhost
    自检不通过而直接退出。这里把 bool 形式的 schema 容错成 Any。
    """
    try:
        import gradio_client.utils as client_utils
    except Exception:
        return

    impl = getattr(client_utils, "_json_schema_to_python_type", None)
    if impl is None or getattr(impl, "_tolerant_patch", False):
        return

    def _tolerant(schema, defs):
        if isinstance(schema, bool):
            return "Any"
        return impl(schema, defs)

    _tolerant._tolerant_patch = True
    client_utils._json_schema_to_python_type = _tolerant


def _chatbot_kwargs() -> Dict[str, Any]:
    """按 Gradio 版本构造 Chatbot 参数（4.x 默认 tuples 格式，需显式 messages）。"""
    params = inspect.signature(gr.Chatbot.__init__).parameters
    kwargs: Dict[str, Any] = {"label": "问答", "height": 520}
    if "placeholder" in params:
        kwargs["placeholder"] = "加载文档后，在下方输入问题……"
    if "type" in params:
        kwargs["type"] = "messages"
    return kwargs


# ---------------------------------------------------------------------------
# 事件处理函数
# ---------------------------------------------------------------------------


def load_document(
    file_path: Optional[str],
    assistant: Optional[PDFLearningAssistant],
    user_id: str,
) -> Tuple[str, PDFLearningAssistant]:
    """加载上传的 PDF 到知识库。"""
    if not file_path:
        return "⚠️ 请先上传 PDF 文件。", assistant

    assistant = _resolve_assistant(assistant, user_id)
    result = assistant.load_document(str(file_path))

    status = result["message"]
    if result.get("details"):
        status = f"{status}\n\n{result['details']}"
    status += _degraded_notice(assistant)
    return status, assistant


def chat(
    message: str,
    history: Optional[List[Dict[str, Any]]],
    assistant: Optional[PDFLearningAssistant],
    user_id: str,
    use_advanced_search: bool,
) -> Tuple[List[Dict[str, Any]], str, PDFLearningAssistant]:
    """向当前文档提问，返回更新后的对话历史。"""
    message = (message or "").strip()
    history = list(history or [])
    if not message:
        return history, "", assistant

    assistant = _resolve_assistant(assistant, user_id)
    answer = assistant.ask(message, use_advanced_search=bool(use_advanced_search))

    history.append({"role": "user", "content": message})
    history.append({"role": "assistant", "content": answer})
    return history, "", assistant


def add_note(
    note: str,
    concept: str,
    assistant: Optional[PDFLearningAssistant],
    user_id: str,
) -> Tuple[str, PDFLearningAssistant]:
    """把一条学习笔记写入语义记忆。"""
    note = (note or "").strip()
    if not note:
        return "⚠️ 笔记内容不能为空。", assistant

    assistant = _resolve_assistant(assistant, user_id)
    return assistant.add_note(note, concept or None), assistant


def recall_memory(
    query: str,
    assistant: Optional[PDFLearningAssistant],
    user_id: str,
) -> Tuple[str, PDFLearningAssistant]:
    """按关键词回顾学习记忆。"""
    query = (query or "").strip()
    if not query:
        return "⚠️ 请输入回顾关键词。", assistant

    assistant = _resolve_assistant(assistant, user_id)
    return assistant.recall(query), assistant


def refresh_stats(
    assistant: Optional[PDFLearningAssistant], user_id: str
) -> Tuple[str, PDFLearningAssistant]:
    """刷新左侧学习统计。"""
    assistant = _resolve_assistant(assistant, user_id)
    return _stats_markdown(assistant) + _degraded_notice(assistant), assistant


def build_report(
    assistant: Optional[PDFLearningAssistant], user_id: str
) -> Tuple[Dict[str, Any], Optional[str], PDFLearningAssistant]:
    """生成学习报告（JSON + 文件下载）。"""
    assistant = _resolve_assistant(assistant, user_id)
    report = assistant.generate_report(save_to_file=True)
    return report, report.get("report_file"), assistant


def clear_chat() -> Tuple[List[Any], str]:
    """清空对话框。"""
    return [], ""


# ---------------------------------------------------------------------------
# 界面
# ---------------------------------------------------------------------------


def create_app() -> gr.Blocks:
    with gr.Blocks(title="PDF 智能文档问答助手") as demo:
        assistant_state = gr.State(None)

        gr.Markdown(
            "# 📚 PDF 智能文档问答助手\n"
            "基于 hello-agents 的 **MemoryTool + RAGTool**：上传 PDF 后即可提问，"
            "助手会用工作 / 情景 / 语义记忆记录你的学习轨迹。\n"
            "> 首次操作会初始化工具（连接 Qdrant / Neo4j / Embedding），请稍等几秒；"
            "加载大部头 PDF 可能需要几分钟。"
        )

        with gr.Row():
            # ---- 左栏：文档与学习工具 ----
            with gr.Column(scale=1):
                user_id_box = gr.Textbox(
                    value="default_user",
                    label="用户ID（数据隔离）",
                )
                pdf_file = gr.File(
                    label="上传 PDF",
                    file_types=[".pdf"],
                    type="filepath",
                )
                load_btn = gr.Button("📥 加载文档", variant="primary")
                load_status = gr.Textbox(
                    label="文档状态",
                    lines=6,
                    interactive=False,
                )

                with gr.Accordion("📊 学习统计", open=True):
                    stats_btn = gr.Button("刷新统计")
                    stats_box = gr.Markdown("（尚未创建会话）")

                with gr.Accordion("📝 学习笔记", open=False):
                    note_box = gr.Textbox(
                        label="笔记内容",
                        lines=3,
                        placeholder="记录一个概念、结论或心得……",
                    )
                    concept_box = gr.Textbox(
                        label="概念标签（可选）",
                        placeholder="如：注意力机制",
                    )
                    note_btn = gr.Button("添加笔记")
                    note_status = gr.Textbox(
                        show_label=False,
                        lines=2,
                        interactive=False,
                    )

                with gr.Accordion("🔍 回顾学习历程", open=False):
                    recall_query = gr.Textbox(
                        label="关键词",
                        placeholder="如：注意力",
                    )
                    recall_btn = gr.Button("回顾")
                    recall_out = gr.Textbox(
                        show_label=False,
                        lines=6,
                        interactive=False,
                    )

                with gr.Accordion("📄 学习报告", open=False):
                    report_btn = gr.Button("生成学习报告")
                    report_json = gr.JSON(label="报告内容")
                    report_file = gr.File(label="报告文件（可下载）")

            # ---- 右栏：问答 ----
            with gr.Column(scale=2):
                chatbot = gr.Chatbot(**_chatbot_kwargs())
                with gr.Row():
                    msg_box = gr.Textbox(
                        show_label=False,
                        placeholder="向文档提问，回车发送……",
                        scale=4,
                        autofocus=True,
                    )
                    advanced_box = gr.Checkbox(
                        value=True,
                        label="高级检索 (MQE + HyDE)",
                        scale=1,
                    )
                with gr.Row():
                    send_btn = gr.Button("发送", variant="primary")
                    clear_btn = gr.Button("清空对话")

        # ---- 事件绑定 ----
        load_btn.click(
            load_document,
            inputs=[pdf_file, assistant_state, user_id_box],
            outputs=[load_status, assistant_state],
            api_name="load_document",
        )

        chat_inputs = [msg_box, chatbot, assistant_state, user_id_box, advanced_box]
        chat_outputs = [chatbot, msg_box, assistant_state]
        send_btn.click(chat, inputs=chat_inputs, outputs=chat_outputs, api_name="chat")
        msg_box.submit(chat, inputs=chat_inputs, outputs=chat_outputs, api_name="chat_submit")

        clear_btn.click(clear_chat, inputs=None, outputs=[chatbot, msg_box])

        note_btn.click(
            add_note,
            inputs=[note_box, concept_box, assistant_state, user_id_box],
            outputs=[note_status, assistant_state],
            api_name="add_note",
        )

        recall_btn.click(
            recall_memory,
            inputs=[recall_query, assistant_state, user_id_box],
            outputs=[recall_out, assistant_state],
            api_name="recall",
        )

        stats_btn.click(
            refresh_stats,
            inputs=[assistant_state, user_id_box],
            outputs=[stats_box, assistant_state],
            api_name="stats",
        )

        report_btn.click(
            build_report,
            inputs=[assistant_state, user_id_box],
            outputs=[report_json, report_file, assistant_state],
            api_name="report",
        )

    return demo


def main() -> None:
    _patch_gradio_matplotlib_manager()
    _patch_gradio_api_info()
    try:
        import matplotlib  # 预热：避免工作线程里首次导入 matplotlib 失败

        matplotlib.use("agg")
    except Exception:
        pass

    demo = create_app()
    demo.queue()
    demo.launch(
        server_name="127.0.0.1",
        server_port=7860,
        allowed_paths=[str(EXPERIMENT_DIR)],
        show_error=True,
        inbrowser=False,
    )


if __name__ == "__main__":
    main()
