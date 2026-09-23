"""hello-agents 0.2.0 / 0.2.8 的框架缺陷补丁（不改动 site-packages）。

本模块集中处理三个实测确认、且都会阻塞「PDF 问答助手」的框架缺陷。
每个补丁都是幂等的，`PDFLearningAssistant` 初始化时会调用
`apply_framework_fixes()` 一次性应用。

1. 分块器死循环（chunk fix）
   `hello_agents.memory.rag.pipeline._chunk_paragraphs` 在「单个段落长度超过
   chunk_size - overlap」时不会推进索引 `i`：输出当前 chunk 后重建的 overlap
   尾巴仍然装不下下一个段落，同一批段落被反复输出，CPU 打满、内存无限增长。
   修复：① 预先把超长段落切成不超过 chunk_tokens 的片段（优先在换行 / 句末
   标点处切）；② 重建 overlap 后若仍放不下下一个段落，放弃 overlap，保证 `i`
   前进。

2. Embedding 批量超限（embedding fix）
   DashScope 兼容接口（EMBED_BASE_URL 走 /embeddings）单请求最多 10 条文本，
   而框架 `index_chunks` 默认按 64 条一批调用：每一批都报
   `batch size is invalid, it should not be larger than 10`，再退化为 8 条一批
   并 sleep 重试，写入速度大幅下降。修复：包装 `DashScopeEmbedding.encode`，
   自动按 ≤10 条拆分请求，整批失败时逐条降级。

3. PDF 解析失败的兜底污染（convert guard）
   MarkItDown 的 PDF 转换器需要 `pdfminer` + `pdfplumber`，缺依赖或转换失败时
   管道会退化为「把 PDF 当纯文本读」，把二进制流写进向量库。修复：对 .pdf 文件
   识别这种回退产物（以 %PDF 开头），直接丢弃并返回空文本，让上层明确报
   「未能从文件解析内容」，而不是写入垃圾向量。

用法
----
    from core.framework_fixes import apply_framework_fixes
    apply_framework_fixes()
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from hello_agents.memory.rag import pipeline as rag_pipeline
from hello_agents.memory.rag.pipeline import _approx_token_len

__all__ = [
    "apply_framework_fixes",
    "apply_chunk_fix",
    "apply_embedding_fix",
    "apply_convert_guard",
]

# DashScope 兼容接口单请求的文本条数上限（实测报错信息：should not be larger than 10）
MAX_EMBED_BATCH = 10


# ---------------------------------------------------------------------------
# 1. 分块器修复
# ---------------------------------------------------------------------------


def _emit_chunk(cur: List[Dict]) -> Dict:
    """与原实现一致的 chunk 组装。"""
    content = "\n\n".join(x["content"] for x in cur)
    start = cur[0]["start"]
    end = cur[-1]["end"]
    heading_path = next(
        (x["heading_path"] for x in reversed(cur) if x.get("heading_path")),
        None,
    )
    return {
        "content": content,
        "start": start,
        "end": end,
        "heading_path": heading_path,
    }


def _split_text(text: str, limit: int) -> List[str]:
    """把超长文本切成不超过 limit 个近似 token 的片段（优先句末切分）。"""
    pieces: List[str] = []
    pos = 0
    size = len(text)
    while pos < size:
        end = min(size, pos + limit)
        if end < size:
            window = text[pos:end]
            cut = max(
                window.rfind("\n"),
                window.rfind("。"),
                window.rfind("！"),
                window.rfind("？"),
                window.rfind("；"),
            )
            if cut >= limit // 2:
                end = pos + cut + 1
        pieces.append(text[pos:end])
        pos = end
    return pieces


def _split_oversized_paragraphs(paragraphs: List[Dict], chunk_tokens: int) -> List[Dict]:
    """预先把超过 chunk_tokens 的段落切分，避免产生超长 chunk。"""
    out: List[Dict] = []
    for p in paragraphs:
        content = p["content"]
        if _approx_token_len(content) <= chunk_tokens:
            out.append(p)
            continue
        start = p.get("start", 0)
        for piece in _split_text(content, chunk_tokens):
            if not piece.strip():
                continue
            out.append(
                {
                    "content": piece,
                    "heading_path": p.get("heading_path"),
                    "start": start,
                    "end": start + len(piece),
                }
            )
            start += len(piece)
    return out


def _chunk_paragraphs_fixed(
    paragraphs: List[Dict], chunk_tokens: int, overlap_tokens: int
) -> List[Dict]:
    """保证索引前进的分块实现（接口与 0.2.0 原函数一致）。"""
    paragraphs = _split_oversized_paragraphs(paragraphs, chunk_tokens)

    chunks: List[Dict] = []
    cur: List[Dict] = []
    cur_tokens = 0
    i = 0

    while i < len(paragraphs):
        p = paragraphs[i]
        p_tokens = _approx_token_len(p["content"]) or 1

        if cur_tokens + p_tokens <= chunk_tokens or not cur:
            cur.append(p)
            cur_tokens += p_tokens
            i += 1
            continue

        # 当前 chunk 已满：先输出
        chunks.append(_emit_chunk(cur))

        # 重建 overlap 尾巴（与原实现一致）
        kept: List[Dict] = []
        kept_tokens = 0
        if overlap_tokens > 0:
            for x in reversed(cur):
                t = _approx_token_len(x["content"]) or 1
                if kept_tokens + t > overlap_tokens:
                    break
                kept.append(x)
                kept_tokens += t
            kept.reverse()

        # 修复点：尾巴 + 下一个段落仍放不进 chunk 时放弃 overlap，保证 i 前进
        if kept and kept_tokens + p_tokens > chunk_tokens:
            kept, kept_tokens = [], 0
        cur, cur_tokens = kept, kept_tokens

    if cur:
        chunks.append(_emit_chunk(cur))
    return chunks


def apply_chunk_fix() -> None:
    """替换 `_chunk_paragraphs` 为修复版（幂等；目标不存在时跳过）。"""
    if not hasattr(rag_pipeline, "_chunk_paragraphs"):
        return
    if getattr(rag_pipeline, "_chunk_paragraphs", None) is _chunk_paragraphs_fixed:
        return
    rag_pipeline._chunk_paragraphs = _chunk_paragraphs_fixed


# ---------------------------------------------------------------------------
# 2. Embedding 批量修复
# ---------------------------------------------------------------------------

from hello_agents.memory.embedding import DashScopeEmbedding

_ORIGINAL_ENCODE = DashScopeEmbedding.encode


def _encode_batched(self, texts):
    """按 ≤ MAX_EMBED_BATCH 条拆分请求；整批失败时逐条降级。"""
    if isinstance(texts, str) or not texts:
        return _ORIGINAL_ENCODE(self, texts)

    items = list(texts)
    results: List[Any] = []
    for i in range(0, len(items), MAX_EMBED_BATCH):
        part = items[i : i + MAX_EMBED_BATCH]
        try:
            vecs = _ORIGINAL_ENCODE(self, part)
        except Exception:
            vecs = None
        if vecs is None or len(vecs) != len(part):
            vecs = []
            for item in part:
                vecs.extend(_ORIGINAL_ENCODE(self, [item]))
        results.extend(vecs)
    return results


def apply_embedding_fix() -> None:
    """包装 `DashScopeEmbedding.encode` 限制单请求条数（幂等；目标不存在时跳过）。"""
    if not hasattr(DashScopeEmbedding, "encode"):
        return
    if getattr(DashScopeEmbedding, "encode", None) is _encode_batched:
        return
    DashScopeEmbedding.encode = _encode_batched


# ---------------------------------------------------------------------------
# 3. PDF 兜底污染防护
# ---------------------------------------------------------------------------

_ORIGINAL_CONVERT = rag_pipeline._convert_to_markdown


def _convert_to_markdown_guarded(path: str) -> str:
    """对 .pdf 识别「把文件当纯文本读」的兜底产物并丢弃。"""
    text = _ORIGINAL_CONVERT(path)
    ext = (os.path.splitext(path)[1] or "").lower()
    if ext == ".pdf" and text and text.lstrip().startswith("%PDF"):
        return ""
    return text


def apply_convert_guard() -> None:
    """替换 `_convert_to_markdown` 为带 PDF 兜底防护的版本（幂等；目标不存在时跳过）。"""
    if not hasattr(rag_pipeline, "_convert_to_markdown"):
        return
    if getattr(rag_pipeline, "_convert_to_markdown", None) is _convert_to_markdown_guarded:
        return
    rag_pipeline._convert_to_markdown = _convert_to_markdown_guarded


# ---------------------------------------------------------------------------
# 汇总入口
# ---------------------------------------------------------------------------


def apply_framework_fixes() -> None:
    """应用全部补丁（幂等，可重复调用；单个补丁失败不影响其余）。"""
    patches = (
        ("chunk", apply_chunk_fix),
        ("embedding", apply_embedding_fix),
        ("convert", apply_convert_guard),
    )
    for name, apply in patches:
        try:
            apply()
        except Exception as exc:  # 兼容未来版本：补丁失败只提示，不阻塞助手
            print(f"[framework_fixes] {name} 补丁应用失败，已跳过: {exc}")
