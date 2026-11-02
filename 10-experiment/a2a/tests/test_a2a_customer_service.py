"""真实 API 集成测试：会调用根目录 .env 中的模型并产生 API 用量。"""

from pathlib import Path
import socket
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "demos"))

from a2a_customer_service import (  # noqa: E402
    create_experts, create_receptionist, load_llm, normalize_question, start_experts,
)
from hello_agents.tools import A2ATool  # noqa: E402


class RecordingA2ATool(A2ATool):
    """真实调用 HTTP 专家服务，同时记录实际调用及返回内容。"""

    def __init__(self, original, calls):
        super().__init__(original.agent_url, original.name, original.description)
        self.calls = calls

    def run(self, parameters):
        result = super().run(parameters)
        self.calls.append((self.name, dict(parameters), result))
        return result


class CustomerServiceLiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.llm = load_llm()  # 配置缺失时失败，不跳过或改用 FakeLLM。
        with socket.socket() as first, socket.socket() as second:
            first.bind(("127.0.0.1", 0))
            second.bind(("127.0.0.1", 0))
            ports = (first.getsockname()[1], second.getsockname()[1])
        cls.urls = start_experts(create_experts(), ports)

    def setUp(self):
        self.agent = create_receptionist(self.llm, self.urls)
        self.calls = []
        for name in ("tech_expert", "sales_advisor"):
            original = self.agent.tool_registry.get_tool(name)
            self.agent.tool_registry.unregister(name)
            self.agent.add_tool(RecordingA2ATool(original, self.calls))

    def ask_and_check(self, question, expected):
        answer = self.agent.run(question)
        self.assertIsInstance(answer, str)
        self.assertTrue(answer.strip())
        self.assertNotIn("[TOOL_CALL:", answer)
        self.assertEqual({name for name, _, _ in self.calls}, expected)
        for name, parameters, result in self.calls:
            self.assertEqual(parameters.get("action"), "ask")
            self.assertTrue(parameters.get("question"))
            self.assertIn("技术专家资料" if name == "tech_expert" else "销售顾问资料", result)
        print(f"\n验证通过：{question}\n实际分流：{sorted(expected)}\n答复：{answer}", flush=True)
        return answer

    def test_api_question(self):
        self.ask_and_check("你们的API如何调用？", {"tech_expert"})

    def test_enterprise_price(self):
        answer = self.ask_and_check("企业版的价格是多少？", {"sales_advisor"})
        self.assertTrue(any(word in answer for word in ("未", "无法", "暂无", "没有", "报价", "确认")))

    def test_python_and_follow_up(self):
        self.ask_and_check("如何集成到我的Python项目中？", {"tech_expert"})
        self.calls.clear()
        self.ask_and_check("那调用返回401怎么办？", {"tech_expert"})
        self.agent.clear_history()
        self.assertEqual(self.agent.get_history(), [])

    def test_mixed_question(self):
        self.ask_and_check("我想了解Python集成方法，也想知道企业版价格。", {"tech_expert", "sales_advisor"})

    def test_greeting(self):
        self.ask_and_check("你好！", set())

    def test_multiline_and_empty_question(self):
        self.assertEqual(normalize_question("answer 第一行\n第二行"), "第一行\n第二行")
        experts = create_experts()
        self.assertIn("请提供", experts[0].skills["answer"](" "))
        self.assertIn("请提供", experts[1].skills["answer"]("answer "))


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    unittest.main(verbosity=2)
