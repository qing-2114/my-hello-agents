"""Offline tests for the LangGraph search workflow."""

import sys
import unittest
from pathlib import Path

from langchain_core.messages import AIMessage

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from LangGraph.graph import run_search  # noqa: E402


class FakeLLM:
    def __init__(self):
        self.calls = []

    def invoke(self, messages):
        prompt = messages[0].content
        self.calls.append(prompt)
        if "分析用户的查询" in prompt:
            return AIMessage(content="理解：用户想了解 LangGraph 全局状态\n搜索词：LangGraph global state")
        return AIMessage(content="LangGraph 使用状态在节点之间传递数据。")


class FakeTavily:
    def __init__(self):
        self.calls = []

    def search(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "answer": "状态用于在节点间传递数据。",
            "results": [
                {
                    "title": "LangGraph",
                    "url": "https://example.com/langgraph",
                    "content": "StateGraph example",
                }
            ],
        }


class SearchWorkflowTests(unittest.TestCase):
    def test_linear_workflow_with_injected_clients(self):
        llm = FakeLLM()
        tavily = FakeTavily()
        result = run_search("如何定义 LangGraph 全局状态？", llm=llm, tavily_client=tavily)

        self.assertEqual(result["step"], "completed")
        self.assertEqual(result["user_query"], "用户想了解 LangGraph 全局状态")
        self.assertEqual(result["search_query"], "LangGraph global state")
        self.assertIn("LangGraph 使用状态", result["final_answer"])
        self.assertEqual(len(llm.calls), 2)
        self.assertIn("今天是", llm.calls[0])
        self.assertIn("不要自行添加", llm.calls[0])
        self.assertIn("必须附上搜索结果中的来源链接", llm.calls[1])
        self.assertEqual(tavily.calls[0]["max_results"], 5)
        self.assertEqual(len(result["messages"]), 4)


if __name__ == "__main__":
    unittest.main()
