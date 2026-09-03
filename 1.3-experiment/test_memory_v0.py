"""Three offline use cases for the V0 hand-written memory demo."""

from __future__ import annotations

import unittest

from memory_store import get_memory_context, search_memories
from agent import build_messages, run_agent


class FakeLLM:
    """Deterministic client used to test the loop without an API call."""

    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def generate(self, prompt: str, system_prompt: str) -> str:
        self.calls.append({"prompt": prompt, "system_prompt": system_prompt})
        return (
            "Thought: 已读取用户偏好，直接给出安排。\n"
            "Action: Finish[我会避开博物馆和西湖醋鱼，优先安排户外活动和其他杭州美食。]"
        )


class MemoryV0Tests(unittest.TestCase):
    def test_indoor_activity_preference_is_retrieved(self) -> None:
        memories = search_memories("杭州有哪些博物馆和室内活动？")
        self.assertEqual([memory["id"] for memory in memories], ["m001"])
        _, context = get_memory_context("杭州有哪些博物馆和室内活动？")
        self.assertIn("不喜欢室内活动", context)
        self.assertIn("博物馆", context)

    def test_food_preference_is_retrieved(self) -> None:
        memories = search_memories("杭州有哪些特色美食？")
        self.assertEqual([memory["id"] for memory in memories], ["m002"])
        _, context = get_memory_context("杭州有哪些特色美食？")
        self.assertIn("不喜欢西湖醋鱼", context)

    def test_combined_trip_query_reads_both_preferences(self) -> None:
        memories = search_memories("帮我安排杭州周末，避开博物馆和西湖醋鱼")
        self.assertEqual({memory["id"] for memory in memories}, {"m001", "m002"})
        fake_llm = FakeLLM()
        answer = run_agent(
            "帮我安排杭州周末，避开博物馆和西湖醋鱼。",
            llm=fake_llm,
        )
        self.assertIn("博物馆", answer)
        self.assertIn("西湖醋鱼", answer)
        self.assertEqual(len(fake_llm.calls), 1)
        self.assertIn("m001", fake_llm.calls[0]["system_prompt"])
        self.assertIn("m002", fake_llm.calls[0]["system_prompt"])
        messages = build_messages("帮我安排杭州周末，避开博物馆和西湖醋鱼")
        self.assertEqual(messages[0]["role"], "system")
        # Retrieval is isolated by user_id; another user cannot see demo-user's
        # hand-written records.
        self.assertEqual(search_memories("杭州周末旅行", user_id="another-user"), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
