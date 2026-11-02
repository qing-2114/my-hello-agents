"""真实 HTTP API 测试：运行两个 A2AServer，不使用 Mock，不调用 LLM。"""

import json
from pathlib import Path
import socket
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "demos"))

from a2a_negotiation import A2AClient, call_json, create_agents, start_agents


class NegotiationHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with socket.socket() as first, socket.socket() as second:
            first.bind(("127.0.0.1", 0))
            second.bind(("127.0.0.1", 0))
            ports = (first.getsockname()[1], second.getsockname()[1])
        cls.url1 = f"http://127.0.0.1:{ports[0]}"
        start_agents(create_agents(cls.url1), ports)
        cls.client1 = A2AClient(cls.url1)
        cls.client2 = A2AClient(f"http://127.0.0.1:{ports[1]}")

    def negotiate(self, **kwargs):
        return call_json(self.client2, "negotiate", {
            "task": "开发客服\n包括技术与销售咨询", "deadline": 3,
            "max_deadline": 10, **kwargs,
        })

    def test_counter_proposal_then_confirmation(self):
        result = self.negotiate()
        self.assertEqual(result["status"], "agreed")
        self.assertEqual(result["rounds"], 2)
        self.assertEqual([item["proposal"]["deadline"] for item in result["history"]], [3, 7])
        self.assertEqual(result["agreement"]["deadline"], 7)
        self.assertIn("\n", result["agreement"]["task"])
        self.assertTrue(result["history"][-1]["reply"]["accepted"])

    def test_direct_acceptance(self):
        result = self.negotiate(deadline=8)
        self.assertEqual((result["status"], result["rounds"]), ("agreed", 1))
        self.assertEqual(result["agreement"]["deadline"], 8)

    def test_reject_above_budget(self):
        result = self.negotiate(max_deadline=5)
        self.assertEqual(result["status"], "rejected")
        self.assertNotIn("agreement", result)

    def test_round_limit_is_not_agreement(self):
        result = self.negotiate(max_rounds=1)
        self.assertEqual(result["status"], "max_rounds")
        self.assertNotIn("agreement", result)

    def test_invalid_inputs(self):
        for params in ({"deadline": True}, {"deadline": 0}, {"task": " "},
                       {"max_rounds": 11}, {"max_deadline": 2}):
            with self.subTest(params=params):
                self.assertEqual(self.negotiate(**params)["status"], "error")

    def test_legacy_command(self):
        response = self.client2.execute_skill("negotiate", "negotiate task:编写文档 deadline:3")
        result = json.loads(response["result"])
        self.assertEqual(result["status"], "agreed")
        self.assertEqual(result["agreement"], {"task": "编写文档", "deadline": 7})

    def test_invalid_json_and_expression(self):
        for text in ("{'task': 'test', 'deadline': 7}", "__import__('os').getcwd()", "[]"):
            response = self.client1.execute_skill("propose", text)
            self.assertEqual(json.loads(response["result"])["status"], "error")

    def test_unavailable_peer(self):
        # 对一个只绑定但未监听的端口发请求，验证真实连接失败分支。
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            url = f"http://127.0.0.1:{probe.getsockname()[1]}"
            _, agent2 = create_agents(url)
            result = json.loads(agent2.skills["negotiate"]('{"task":"test","deadline":3}'))
        self.assertEqual(result["status"], "error")
        self.assertIn("服务调用失败", result["message"])
        self.assertNotIn("agreement", result)


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    unittest.main(verbosity=2)
