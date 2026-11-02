"""ANP 负载均衡策略的确定性测试。"""

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "demos"))
from anp_load_balancer import allocate_requests, create_discovery, get_best_server
from hello_agents.protocols import ANPDiscovery


class LoadBalancerTests(unittest.TestCase):
    def test_requests_follow_lowest_updated_load(self):
        discovery = create_discovery()
        services = discovery.list_all_services()
        for server in services:
            server.metadata["load"] = 0.9
        services[0].metadata["load"] = 0.1
        services[1].metadata["load"] = 0.15
        allocations = allocate_requests(discovery, 3, 0.1)
        self.assertEqual([server.service_id for server, _ in allocations],
                         ["api_server_0", "api_server_1", "api_server_0"])
        self.assertAlmostEqual(services[0].metadata["load"], 0.3)
        self.assertAlmostEqual(services[1].metadata["load"], 0.25)

    def test_no_services_returns_no_server(self):
        self.assertIsNone(get_best_server(ANPDiscovery()))

    def test_zero_increment_keeps_selecting_first_minimum(self):
        discovery = create_discovery()
        allocations = allocate_requests(discovery, 3, 0)
        self.assertEqual(len({server.service_id for server, _ in allocations}), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
