"""离线单元测试：core/framework_fixes.py 的三个框架补丁。

运行（在 8-experiment 目录下）：

    F:/my-hello-agent/.conda/python.exe -m unittest test_framework_fixes -v
"""

from __future__ import annotations

import multiprocessing as mp
import sys
import unittest
from pathlib import Path

EXPERIMENT_DIR = Path(__file__).resolve().parent
if str(EXPERIMENT_DIR) not in sys.path:
    sys.path.insert(0, str(EXPERIMENT_DIR))

from core import framework_fixes
from core.framework_fixes import (
    _approx_token_len,
    _chunk_paragraphs_fixed,
    _convert_to_markdown_guarded,
    _encode_batched,
)


def _hang_probe() -> None:
    """在子进程里跑修复版分块器；若回归为死循环，子进程会被父进程终止。"""
    paragraphs = [
        {"content": "短段落", "start": 0, "end": 3, "heading_path": None},
        {"content": "长" * 1500, "start": 3, "end": 1503, "heading_path": None},
    ]
    chunks = _chunk_paragraphs_fixed(paragraphs, 1000, 200)
    print(f"chunks={len(chunks)}", flush=True)


class ChunkFixTests(unittest.TestCase):
    def test_terminates_on_oversized_paragraph(self):
        process = mp.Process(target=_hang_probe)
        process.start()
        process.join(timeout=40)
        still_running = process.is_alive()
        if still_running:
            process.terminate()
            process.join()
        self.assertFalse(still_running, "修复版分块器超时，疑似回归为死循环")

    def test_splits_oversized_paragraphs(self):
        paragraphs = [
            {"content": "长" * 5000, "start": 0, "end": 5000, "heading_path": "第一章"}
        ]
        chunks = _chunk_paragraphs_fixed(paragraphs, 1000, 200)
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertLessEqual(_approx_token_len(chunk["content"]), 1005)
        joined = "".join(chunk["content"] for chunk in chunks)
        self.assertGreaterEqual(len(joined), 5000)

    def test_packs_short_paragraphs(self):
        paragraphs = [
            {
                "content": "段" * 300,
                "start": i * 300,
                "end": (i + 1) * 300,
                "heading_path": None,
            }
            for i in range(5)
        ]
        chunks = _chunk_paragraphs_fixed(paragraphs, 1000, 200)
        self.assertGreaterEqual(len(chunks), 1)
        for chunk in chunks:
            self.assertLessEqual(_approx_token_len(chunk["content"]), 1005)


class EmbeddingFixTests(unittest.TestCase):
    def test_splits_requests_and_preserves_order(self):
        recorded = []

        def fake_original(self, texts):
            if isinstance(texts, str):
                return [1]
            recorded.append(len(texts))
            return [len(texts)] * len(texts)

        original = framework_fixes._ORIGINAL_ENCODE
        framework_fixes._ORIGINAL_ENCODE = fake_original
        try:
            vectors = _encode_batched(object(), [f"t{i}" for i in range(25)])
        finally:
            framework_fixes._ORIGINAL_ENCODE = original

        self.assertEqual(len(vectors), 25)
        self.assertTrue(
            all(n <= framework_fixes.MAX_EMBED_BATCH for n in recorded), recorded
        )
        self.assertEqual(sum(recorded), 25)

    def test_falls_back_to_single_items_on_batch_failure(self):
        def fake_original(self, texts):
            if isinstance(texts, str):
                return [0]
            if len(texts) > 1:
                raise RuntimeError("batch rejected")
            return [0]

        original = framework_fixes._ORIGINAL_ENCODE
        framework_fixes._ORIGINAL_ENCODE = fake_original
        try:
            vectors = _encode_batched(object(), [f"t{i}" for i in range(12)])
        finally:
            framework_fixes._ORIGINAL_ENCODE = original
        self.assertEqual(len(vectors), 12)


class ConvertGuardTests(unittest.TestCase):
    def test_discards_binary_pdf_fallback(self):
        original = framework_fixes._ORIGINAL_CONVERT
        framework_fixes._ORIGINAL_CONVERT = lambda path: "%PDF-1.7\nbinary garbage"
        try:
            self.assertEqual(_convert_to_markdown_guarded("book.pdf"), "")
        finally:
            framework_fixes._ORIGINAL_CONVERT = original

    def test_keeps_normal_text(self):
        original = framework_fixes._ORIGINAL_CONVERT
        framework_fixes._ORIGINAL_CONVERT = lambda path: "# 标题\n正文内容"
        try:
            self.assertEqual(
                _convert_to_markdown_guarded("book.pdf"), "# 标题\n正文内容"
            )
            self.assertEqual(
                _convert_to_markdown_guarded("notes.txt"), "# 标题\n正文内容"
            )
        finally:
            framework_fixes._ORIGINAL_CONVERT = original


if __name__ == "__main__":
    unittest.main()
