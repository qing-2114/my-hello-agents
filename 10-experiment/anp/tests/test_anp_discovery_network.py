"""ANP 服务发现与组网的离线测试。

纯内存拓扑，不启动服务、不发起网络请求、不调用 LLM，因此不需要真实 API。
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "demos"))

from hello_agents.protocols import ServiceInfo

from anp_network import add_node, build_network, connect, connect_by_capability
from anp_service_discovery import create_discovery, find_services, select_best_service


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.discovery = create_discovery()

    def ids(self, services):
        return [service.service_id for service in services]

    def test_register_all_services(self):
        self.assertEqual(
            self.ids(self.discovery.list_all_services()),
            ["nlp_agent_1", "nlp_agent_2", "translate_agent", "router_agent"],
        )

    def test_find_by_type(self):
        services = find_services(self.discovery, service_type="nlp")
        self.assertEqual(self.ids(services), ["nlp_agent_1", "nlp_agent_2"])

    def test_find_by_unknown_type(self):
        self.assertEqual(find_services(self.discovery, service_type="vision"), [])

    def test_find_by_capability(self):
        services = find_services(self.discovery, capability="translation")
        self.assertEqual(self.ids(services), ["nlp_agent_2", "translate_agent"])

    def test_find_by_type_and_capability(self):
        services = find_services(self.discovery, service_type="nlp", capability="translation")
        self.assertEqual(self.ids(services), ["nlp_agent_2"])

    def test_find_by_metadata(self):
        services = find_services(self.discovery, version="1.1.0")
        self.assertEqual(self.ids(services), ["nlp_agent_2"])

    def test_select_best_by_load(self):
        best = select_best_service(find_services(self.discovery, service_type="nlp"))
        self.assertEqual(best.service_id, "nlp_agent_1")

    def test_select_best_on_empty_list(self):
        self.assertIsNone(select_best_service([]))

    def test_missing_or_invalid_load_sorts_last(self):
        unknown = ServiceInfo("unknown", "nlp", "http://localhost:9001", metadata={"price": 0.001})
        invalid = ServiceInfo("invalid", "nlp", "http://localhost:9002", metadata={"load": "0.1"})
        known = ServiceInfo("known", "nlp", "http://localhost:9003", metadata={"load": 0.9})
        self.assertEqual(select_best_service([unknown, invalid, known]).service_id, "known")

    def test_price_breaks_load_tie(self):
        cheap = ServiceInfo("cheap", "nlp", "http://localhost:9004",
                            metadata={"load": 0.5, "price": 0.01})
        pricey = ServiceInfo("pricey", "nlp", "http://localhost:9005",
                             metadata={"load": 0.5, "price": 0.09})
        self.assertEqual(select_best_service([pricey, cheap]).service_id, "cheap")


class NetworkTests(unittest.TestCase):
    def setUp(self):
        self.discovery = create_discovery()
        self.network = build_network(self.discovery)

    def connections(self, node_id):
        return self.network.get_node_info(node_id)["connections"]

    def test_build_network(self):
        stats = self.network.get_network_stats()
        self.assertEqual(stats["network_id"], "ai_cluster")
        self.assertEqual(stats["total_nodes"], 4)
        self.assertEqual(stats["active_nodes"], 4)
        self.assertEqual(stats["total_connections"], 0)
        self.assertEqual(self.network.get_node_info("nlp_agent_1")["endpoint"], "http://localhost:8001")

    def test_duplicate_node_rejected(self):
        connect(self.network, "nlp_agent_1", "nlp_agent_2")
        with self.assertRaises(ValueError):
            add_node(self.network, "nlp_agent_1", "http://localhost:9999")
        # 失败不应破坏已有连接
        self.assertEqual(self.connections("nlp_agent_1"), ["nlp_agent_2"])

    def test_connect_missing_node_rejected(self):
        with self.assertRaises(KeyError):
            connect(self.network, "nlp_agent_1", "vision_agent")
        self.assertEqual(self.connections("nlp_agent_1"), [])

    def test_connect_is_bidirectional_and_idempotent(self):
        self.assertTrue(connect(self.network, "nlp_agent_1", "nlp_agent_2"))
        self.assertEqual(self.connections("nlp_agent_1"), ["nlp_agent_2"])
        self.assertEqual(self.connections("nlp_agent_2"), ["nlp_agent_1"])
        self.assertFalse(connect(self.network, "nlp_agent_1", "nlp_agent_2"))
        self.assertEqual(self.connections("nlp_agent_1"), ["nlp_agent_2"])

    def test_connect_by_capability(self):
        edges = connect_by_capability(self.network, self.discovery)
        pairs = {(left, right) for left, right, _ in edges}
        self.assertIn(("nlp_agent_1", "nlp_agent_2"), pairs)
        self.assertIn(("nlp_agent_1", "translate_agent"), pairs)
        self.assertIn(("nlp_agent_2", "translate_agent"), pairs)
        # router 的能力与其他服务没有交集，不应被自动连接
        self.assertEqual(self.connections("router_agent"), [])
        self.assertEqual(len(pairs), 3)

    def test_capability_matching_is_symmetric(self):
        connect_by_capability(self.network, self.discovery)
        self.assertIn("translate_agent", self.connections("nlp_agent_1"))
        self.assertIn("nlp_agent_1", self.connections("translate_agent"))

    def test_route_direct_and_two_hops(self):
        connect_by_capability(self.network, self.discovery)
        connect(self.network, "router_agent", "nlp_agent_1")
        self.assertEqual(
            self.network.route_message("router_agent", "nlp_agent_1", {}),
            ["router_agent", "nlp_agent_1"],
        )
        self.assertEqual(
            self.network.route_message("router_agent", "nlp_agent_2", {}),
            ["router_agent", "nlp_agent_1", "nlp_agent_2"],
        )

    def test_route_without_path(self):
        self.assertIsNone(self.network.route_message("router_agent", "nlp_agent_1", {}))

    def test_route_to_unknown_node(self):
        connect(self.network, "router_agent", "nlp_agent_1")
        self.assertIsNone(self.network.route_message("router_agent", "vision_agent", {}))

    def test_broadcast(self):
        connect(self.network, "nlp_agent_1", "nlp_agent_2")
        self.assertEqual(self.network.broadcast_message("nlp_agent_1", {}), ["nlp_agent_2"])
        self.assertEqual(self.network.broadcast_message("router_agent", {}), [])
        self.assertEqual(self.network.broadcast_message("vision_agent", {}), [])

    def test_remove_node_cleans_connections(self):
        connect(self.network, "nlp_agent_1", "nlp_agent_2")
        self.assertTrue(self.network.remove_node("nlp_agent_2"))
        self.assertIsNone(self.network.get_node_info("nlp_agent_2"))
        self.assertEqual(self.connections("nlp_agent_1"), [])
        self.assertFalse(self.network.remove_node("nlp_agent_2"))


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    unittest.main(verbosity=2)
