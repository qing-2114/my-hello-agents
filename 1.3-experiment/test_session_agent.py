"""Offline tests for multi-turn rejection and reflection behavior."""

from __future__ import annotations

import unittest

from session_agent import SessionState, classify_feedback, continue_session


class SequencedLLM:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []
        self.recommendation_number = 0

    def generate(self, prompt: str, system_prompt: str) -> str:
        self.calls.append({"prompt": prompt, "system_prompt": system_prompt})
        if "旅行推荐策略调整器" in system_prompt:
            return "避开前三个拥挤且偏室内的方案；优先安静户外地点；询问可接受的交通时长。"
        self.recommendation_number += 1
        return f"Thought: 给出新方案。\nAction: Finish[推荐方案{self.recommendation_number}]"


class SessionAgentTests(unittest.TestCase):
    def test_natural_language_feedback_is_classified(self) -> None:
        class ClassifierLLM:
            def generate(self, prompt: str, system_prompt: str) -> str:
                self.prompt = prompt
                self.system_prompt = system_prompt
                return "REJECT"

        llm = ClassifierLLM()
        result = classify_feedback("这个地方人太多，换一个", "推荐西湖", llm)
        self.assertEqual(result, "reject")
        self.assertIn("推荐西湖", llm.prompt)
        self.assertIn("反馈分类器", llm.system_prompt)

    def test_first_message_is_not_feedback(self) -> None:
        result = classify_feedback("推荐一个杭州景点", None, object())
        self.assertEqual(result, "none")

    def test_third_consecutive_rejection_triggers_reflection(self) -> None:
        llm = SequencedLLM()
        state = SessionState(session_id="s-1")

        continue_session(state, "推荐一个杭州景点", llm=llm)
        first = continue_session(state, "人太多", feedback_type="reject", llm=llm)
        second = continue_session(state, "还是太商业化", feedback_type="reject", llm=llm)
        third = continue_session(state, "我也不想去室内", feedback_type="reject", llm=llm)

        self.assertFalse(first.reflected)
        self.assertFalse(second.reflected)
        self.assertTrue(third.reflected)
        self.assertEqual(third.consecutive_rejections, 0)
        self.assertEqual(third.strategy_version, 1)
        self.assertIn("优先安静户外地点", state.strategy_context)
        self.assertIn("# 当前会话的策略调整", llm.calls[-1]["system_prompt"])
        self.assertIn("历史assistant: 推荐方案1", llm.calls[-1]["prompt"])
        reflection_call = next(
            call for call in llm.calls if "旅行推荐策略调整器" in call["system_prompt"]
        )
        self.assertIn("不喜欢室内活动", reflection_call["prompt"])
        self.assertIn("不得推断用户拒绝了整个活动类别", reflection_call["prompt"])

    def test_strategy_update_callback_runs_before_answer_generation(self) -> None:
        events: list[str] = []

        class EventLLM(SequencedLLM):
            def generate(self, prompt: str, system_prompt: str) -> str:
                if "旅行推荐策略调整器" not in system_prompt:
                    events.append("answer")
                return super().generate(prompt, system_prompt)

        llm = EventLLM()
        state = SessionState(session_id="s-events")
        continue_session(state, "推荐一个杭州景点", llm=llm)
        continue_session(state, "不要", feedback_type="reject", llm=llm)
        continue_session(state, "都不要", feedback_type="reject", llm=llm)
        events.clear()
        continue_session(
            state,
            "不好玩",
            feedback_type="reject",
            llm=llm,
            on_strategy_updated=lambda strategy: events.append("strategy"),
        )
        self.assertEqual(events, ["strategy", "answer"])

    def test_acceptance_resets_rejection_streak(self) -> None:
        llm = SequencedLLM()
        state = SessionState(session_id="s-2")
        continue_session(state, "推荐景点", llm=llm)
        continue_session(state, "不喜欢", feedback_type="reject", llm=llm)
        result = continue_session(state, "这个可以", feedback_type="accept", llm=llm)
        self.assertEqual(result.consecutive_rejections, 0)
        self.assertEqual(state.recent_rejections, [])

    def test_relevant_memory_remains_available_on_short_follow_up(self) -> None:
        llm = SequencedLLM()
        state = SessionState(session_id="s-memory")
        continue_session(state, "推荐一个杭州景点", llm=llm)
        continue_session(state, "不要", feedback_type="reject", llm=llm)

        self.assertIn("m001", llm.calls[-1]["system_prompt"])
        self.assertIn("不喜欢室内活动", llm.calls[-1]["system_prompt"])

    def test_reject_without_recommendation_is_invalid(self) -> None:
        with self.assertRaisesRegex(ValueError, "没有可拒绝的推荐"):
            continue_session(
                SessionState(session_id="s-3"),
                "不喜欢",
                feedback_type="reject",
                llm=SequencedLLM(),
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
