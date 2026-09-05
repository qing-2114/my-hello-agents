"""ReAct Agent 的离线核心循环测试。"""

import sys
import unittest
from pathlib import Path


REACT_DIR = Path(__file__).resolve().parent
if str(REACT_DIR) not in sys.path:
    sys.path.insert(0, str(REACT_DIR))

from agent import ReActAgent
from tools import ToolExecutor


class FakeLLM:
    def __init__(self, responses: list[str]) -> None:
        self.responses = responses.copy()
        self.messages: list[list[dict[str, str]]] = []

    def think(self, messages: list[dict[str, str]]) -> str:
        self.messages.append(messages)
        return self.responses.pop(0)


class ReActAgentTests(unittest.TestCase):
    def test_output_parser_extracts_thought_action_and_tool_input(self) -> None:
        agent = ReActAgent(FakeLLM([]), ToolExecutor())

        thought, action = agent._parse_output(
            "Thought: 需要查询最新信息。\nAction: Search[英伟达最新 GPU]"
        )
        tool_name, tool_input = agent._parse_action(action or "")

        self.assertEqual(thought, "需要查询最新信息。")
        self.assertEqual(action, "Search[英伟达最新 GPU]")
        self.assertEqual(tool_name, "Search")
        self.assertEqual(tool_input, "英伟达最新 GPU")

    def test_tool_observation_is_available_to_the_next_step(self) -> None:
        executor = ToolExecutor()
        executor.registerTool("Search", "搜索实时信息", lambda query: f"搜索结果: {query}")
        llm = FakeLLM(
            [
                "Thought: 需要先查询。\nAction: Search[英伟达最新的 GPU]",
                "Finish[英伟达最新的 GPU 是模拟结果。]",
            ]
        )
        agent = ReActAgent(llm, executor, max_steps=2)

        answer = agent.run("英伟达最新的 GPU 型号是什么？")

        self.assertEqual(answer, "英伟达最新的 GPU 是模拟结果。")
        self.assertIn(
            "Observation: 搜索结果: 英伟达最新的 GPU",
            llm.messages[1][0]["content"],
        )

    def test_output_parser_accepts_direct_finish(self) -> None:
        agent = ReActAgent(FakeLLM([]), ToolExecutor())

        thought, action = agent._parse_output("Finish[深圳今天多云，气温 24-30℃。]")

        self.assertIsNone(thought)
        self.assertEqual(action, "Finish[深圳今天多云，气温 24-30℃。]")

    def test_invalid_action_becomes_an_observation(self) -> None:
        executor = ToolExecutor()
        llm = FakeLLM(
            [
                "Thought: 格式错误。\nAction: Search(英伟达)",
                "Thought: 已修正。\nAction: Finish[已完成。]",
            ]
        )
        agent = ReActAgent(llm, executor, max_steps=2)

        answer = agent.run("测试格式修正")

        self.assertEqual(answer, "已完成。")
        self.assertIn("Action 必须是 工具名[工具输入]", llm.messages[1][0]["content"])

    def test_max_steps_returns_none(self) -> None:
        executor = ToolExecutor()
        executor.registerTool("Search", "搜索实时信息", lambda query: "仍需继续")
        llm = FakeLLM(["Thought: 查询。\nAction: Search[继续]"])
        agent = ReActAgent(llm, executor, max_steps=1)

        answer = agent.run("持续查询")

        self.assertIsNone(answer)

    def test_missing_action_ends_the_run(self) -> None:
        llm = FakeLLM(["Thought: 没有按照格式提供行动。"])
        agent = ReActAgent(llm, ToolExecutor(), max_steps=2)

        answer = agent.run("测试缺失 Action")

        self.assertIsNone(answer)
        self.assertEqual(len(llm.messages), 1)


if __name__ == "__main__":
    unittest.main()
