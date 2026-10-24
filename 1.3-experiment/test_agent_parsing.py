"""Offline tests for Action extraction, including multi-line Finish answers."""

from __future__ import annotations

import unittest

from agent import extract_action, parse_action, run_agent


class ScriptedLLM:
    def __init__(self, outputs: list[str]) -> None:
        self.outputs = list(outputs)
        self.calls = 0

    def generate(self, prompt: str, system_prompt: str) -> str:
        self.calls += 1
        return self.outputs.pop(0)


class ExtractActionTests(unittest.TestCase):
    def test_single_line_tool_call(self) -> None:
        text = 'Thought: 查天气。\nAction: get_weather(city="杭州")\n'
        self.assertEqual(extract_action(text), 'get_weather(city="杭州")')

    def test_multi_line_finish_keeps_whole_answer(self) -> None:
        text = "Thought: 可以回答了。\nAction: Finish[第一行\n\n第二行]"
        self.assertEqual(parse_action(extract_action(text)), "第一行\n\n第二行")

    def test_chatter_after_finish_is_dropped(self) -> None:
        text = (
            "Thought: 完成。\nAction: Finish[推荐灵隐寺\n请带雨具。]\n\n"
            "Wait, I should keep format. Let me output correctly."
        )
        self.assertEqual(parse_action(extract_action(text)), "推荐灵隐寺\n请带雨具。")

    def test_nested_brackets_in_finish(self) -> None:
        text = "Action: Finish[备选:\n[1] 九溪十八涧\n[2] 西溪湿地]"
        self.assertEqual(
            parse_action(extract_action(text)), "备选:\n[1] 九溪十八涧\n[2] 西溪湿地"
        )

    def test_missing_action_returns_none(self) -> None:
        self.assertIsNone(extract_action("Thought: 我还在想。"))

    def test_unbalanced_finish_still_reports_error(self) -> None:
        with self.assertRaises(ValueError):
            parse_action(extract_action("Action: Finish[没有闭合\n第二行"))


class RunAgentFinishTests(unittest.TestCase):
    def test_multi_line_finish_ends_loop_in_one_step(self) -> None:
        llm = ScriptedLLM(["Thought: 直接回答。\nAction: Finish[推荐西湖\n建议清晨前往。]"])
        answer = run_agent("推荐一个杭州景点", llm=llm, trace_memory=False)
        self.assertEqual(answer, "推荐西湖\n建议清晨前往。")
        self.assertEqual(llm.calls, 1)


if __name__ == "__main__":
    unittest.main()
