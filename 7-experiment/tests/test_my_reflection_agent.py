"""MyReflectionAgent 的离线测试。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
if str(EXPERIMENT_ROOT) not in sys.path:
    sys.path.insert(0, str(EXPERIMENT_ROOT))

from agents.my_reflection_agent import MyReflectionAgent  # noqa: E402


class FakeLLM:
    provider = "test"
    model = "fake"

    def __init__(self, responses: list[str]) -> None:
        self.responses = iter(responses)
        self.prompts: list[str] = []

    def invoke(self, messages: list[dict[str, str]], **kwargs) -> str:
        self.prompts.append(messages[-1]["content"])
        return next(self.responses)


class MyReflectionAgentTests(unittest.TestCase):
    def test_iterates_for_a_non_code_task(self) -> None:
        llm = FakeLLM([
            "初稿：给出一个学习计划。",
            "缺少具体时间和可执行的检查方式。",
            "改进稿：每天安排固定时段，并在周末复盘完成情况。",
        ])
        agent = MyReflectionAgent("test", llm, max_iterations=1)

        result = agent.run("请设计一个一周学习计划")

        self.assertEqual(result, "改进稿：每天安排固定时段，并在周末复盘完成情况。")
        self.assertEqual(len(llm.prompts), 3)
        self.assertIn("# 当前回答:", llm.prompts[1])
        self.assertIn("# 反馈意见:", llm.prompts[2])
        self.assertEqual(len(agent.get_history()), 2)

    def test_exact_no_improvement_stops_early(self) -> None:
        llm = FakeLLM(["初稿", "无需改进。"])
        agent = MyReflectionAgent("test", llm, max_iterations=3)

        self.assertEqual(agent.run("总结这段文字"), "初稿")
        self.assertEqual(len(llm.prompts), 2)

    def test_extra_feedback_text_does_not_trigger_early_stop(self) -> None:
        llm = FakeLLM(["初稿", "无需改进，但可以补充一个例子。", "改进稿"])
        agent = MyReflectionAgent("test", llm, max_iterations=1)

        self.assertEqual(agent.run("写一段说明"), "改进稿")
        self.assertEqual(len(llm.prompts), 3)

    def test_zero_iterations_only_generates_initial_answer(self) -> None:
        llm = FakeLLM(["初稿"])
        agent = MyReflectionAgent("test", llm, max_iterations=0)

        self.assertEqual(agent.run("翻译一句话"), "初稿")
        self.assertEqual(len(llm.prompts), 1)

    def test_invalid_response_and_configuration_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            MyReflectionAgent("test", FakeLLM([]), max_iterations=-1)
        with self.assertRaises(ValueError):
            MyReflectionAgent("test", FakeLLM([]), custom_prompts={"other": "x"})

        agent = MyReflectionAgent("test", FakeLLM(["   "]), max_iterations=0)
        with self.assertRaises(RuntimeError):
            agent.run("有效任务")


if __name__ == "__main__":
    unittest.main()
