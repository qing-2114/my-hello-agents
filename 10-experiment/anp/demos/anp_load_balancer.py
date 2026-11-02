"""ANP 最低负载选择示例；负载更新仅模拟本地调度。

项目来源：https://hello-agents.datawhale.cc/
负载是可累加的调度分数，可超过 1，不表示实际 CPU 利用率。
"""

import argparse
import random
import sys

from hello_agents.protocols import ANPDiscovery, register_service


def create_discovery(seed: int = 42) -> ANPDiscovery:
    rng = random.Random(seed)
    discovery = ANPDiscovery()
    for i in range(5):
        register_service(
            discovery=discovery,
            service_id=f"api_server_{i}",
            service_name=f"API服务器{i}",
            service_type="api",
            capabilities=["rest_api"],
            endpoint=f"http://api{i}:8000",
            metadata={"load": round(rng.uniform(0.1, 0.9), 3)},
        )
    return discovery


def _load(value) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 1.0
    return float(value)


def get_best_server(discovery: ANPDiscovery):
    """返回当前负载最低的 API 服务；缺少或非法负载按 1.0 处理。"""
    servers = discovery.discover_services(service_type="api")
    if not servers:
        return None
    return min(servers, key=lambda server: _load(server.metadata.get("load")))


def allocate_requests(discovery: ANPDiscovery, count: int = 10, increment: float = 0.1):
    if count < 0 or increment < 0:
        raise ValueError("请求数和负载增量不能为负数")
    allocations = []
    for _ in range(count):
        server = get_best_server(discovery)
        if server is None:
            break
        current = _load(server.metadata.get("load"))
        allocations.append((server, current))
        server.metadata["load"] = round(current + increment, 3)
    return allocations


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--requests", type=int, default=10)
    parser.add_argument("--increment", type=float, default=0.1)
    args = parser.parse_args()
    if args.requests < 0 or args.increment < 0:
        parser.error("--requests 和 --increment 不能为负数")
    discovery = create_discovery(args.seed)
    print(f"已注册 {len(discovery.list_all_services())} 个 API 服务（模拟负载，不发送请求）")
    allocations = allocate_requests(discovery, args.requests, args.increment)
    for index, (server, load) in enumerate(allocations, start=1):
        print(f"请求 {index} -> {server.service_name} (分配前负载: {load:.3f})")


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    main()
