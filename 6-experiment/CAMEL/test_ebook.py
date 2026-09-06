"""电子书协作辅助函数的离线测试。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import ebook
import main


class FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class FakeResponse:
    def __init__(self, *contents: str) -> None:
        self.msgs = [FakeMessage(content) for content in contents]


class EbookTest(unittest.TestCase):
    def test_response_content_handles_empty_and_single_message(self) -> None:
        self.assertEqual(ebook.response_content(FakeResponse("  内容  ")), "内容")
        self.assertEqual(ebook.response_content(FakeResponse()), "")

    def test_clean_solution_removes_protocol_wrapper(self) -> None:
        content = "Solution:\n## 引言\n拖延并不等于懒惰。\n\nNext request."
        self.assertEqual(ebook.clean_solution(content), "## 引言\n拖延并不等于懒惰。")

    def test_chinese_character_count(self) -> None:
        self.assertEqual(ebook.chinese_character_count("拖延 ABC，心理学 123"), 5)

    def test_upsert_chapter_replaces_same_heading(self) -> None:
        chapters = ["## 实用策略与练习\n不必一次性"]
        ebook.upsert_chapter(chapters, "## 实用策略与练习\n完整正文")
        self.assertEqual(chapters, ["## 实用策略与练习\n完整正文"])

    def test_write_artifacts_keeps_book_and_trace_separate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            with (
                patch.object(ebook, "OUTPUT_DIR", output),
                patch.object(ebook, "EBOOK_PATH", output / "book.md"),
                patch.object(ebook, "TRACE_PATH", output / "trace.md"),
            ):
                book_path, trace_path, count = ebook.write_artifacts(
                    ["## 引言\n拖延并不等于懒惰。"],
                    [("作家", "Instruction: 写引言"), ("心理学家", "Solution: 正文")],
                )
            self.assertEqual(count, 10)
            self.assertIn("拖延并不等于懒惰", book_path.read_text(encoding="utf-8"))
            self.assertNotIn("Instruction:", book_path.read_text(encoding="utf-8"))
            self.assertIn("Instruction: 写引言", trace_path.read_text(encoding="utf-8"))

    def test_agent_step_with_retry_recovers_from_empty_response(self) -> None:
        class FlakyAgent:
            attempts = 0

            def step(self, _input_msg):
                self.attempts += 1
                if self.attempts == 1:
                    return FakeResponse()
                return FakeResponse("完成")

        agent = FlakyAgent()
        with patch.object(main.time, "sleep"):
            result = main.agent_step_with_retry(
                agent, FakeMessage("input"), retries=2, role="心理学家"
            )
        self.assertEqual(ebook.response_content(result), "完成")
        self.assertEqual(agent.attempts, 2)

    def test_terminal_display_protocol_is_stable(self) -> None:
        writer = main.normalize_writer_display("请撰写引言")
        psychologist = main.normalize_psychologist_display("## 引言\n正文")
        self.assertEqual(writer, "Instruction: 请撰写引言\nInput: None")
        self.assertEqual(
            psychologist,
            "Solution:\n## 引言\n正文\n\nNext request.",
        )

    def test_terminal_display_does_not_duplicate_existing_fields(self) -> None:
        writer = "Instruction: 修订引言\nInput: 引言草稿"
        psychologist = "Solution:\n修订稿\n\nNext request."
        self.assertEqual(main.normalize_writer_display(writer), writer)
        self.assertEqual(main.normalize_psychologist_display(psychologist), psychologist)


if __name__ == "__main__":
    unittest.main()
