"""ANP 组网：把服务发现结果建成 Agent 网络，按能力建立双向连接并演示路由。

项目来源：https://hello-agents.datawhale.cc/
本示例全程操作内存中的网络拓扑，不发起网络请求，也不调用 LLM。
"""

import sys
from typing import Any, Dict, List, Optional, Tuple

from hello_agents.protocols import ANPDiscovery, ANPNetwork

from anp_service_discovery import create_discovery, find_services, select_best_service


def add_node(
    network: ANPNetwork,
    node_id: str,
    endpoint: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """添加节点。

    ``ANPNetwork.add_node()`` 遇到同名节点会直接覆盖，并把该节点已有连接清空，
    因此这里先检查，避免重复添加把已经建好的网络打断。
    """
    if network.get_node_info(node_id) is not None:
        raise ValueError(f"节点已存在，不能重复添加: {node_id}")
    network.add_node(node_id, endpoint, metadata)


def connect(network: ANPNetwork, from_node: str, to_node: str) -> bool:
    """建立双向连接，返回本次是否真的新增了连接。

    库的 ``connect_nodes()`` 只建一条单向边，而且节点不存在时静默忽略；
    这里补上存在性检查，并同时建反向边，保证 ``route_message()`` 双向可达。
    """
    for node in (from_node, to_node):
        if network.get_node_info(node) is None:
            raise KeyError(f"节点不存在: {node}")
    added = False
    for source, target in ((from_node, to_node), (to_node, from_node)):
        if target not in network.get_node_info(source)["connections"]:
            network.connect_nodes(source, target)
            added = True
    return added


def build_network(discovery: ANPDiscovery, network_id: str = "ai_cluster") -> ANPNetwork:
    """把服务发现中心里的每个服务注册成网络节点。"""
    network = ANPNetwork(network_id=network_id)
    for service in discovery.list_all_services():
        add_node(
            network,
            service.service_id,
            service.endpoint,
            metadata={
                "service_type": service.service_type,
                "capabilities": list(service.capabilities),
                "load": service.metadata.get("load"),
            },
        )
    return network


def connect_by_capability(
    network: ANPNetwork,
    discovery: ANPDiscovery,
) -> List[Tuple[str, str, List[str]]]:
    """能力有交集的两个服务互连，返回本次新增的边及其共同能力。"""
    services = discovery.list_all_services()
    edges: List[Tuple[str, str, List[str]]] = []
    for index, left in enumerate(services):
        for right in services[index + 1:]:
            shared = sorted(set(left.capabilities) & set(right.capabilities))
            if shared and connect(network, left.service_id, right.service_id):
                edges.append((left.service_id, right.service_id, shared))
    return edges


def print_edges(network: ANPNetwork) -> None:
    for node_id in network.get_network_stats()["nodes"]:
        info = network.get_node_info(node_id)
        print(f"  {node_id:<14} -> {', '.join(info['connections']) or '（无连接）'}")


def demo() -> None:
    discovery = create_discovery()
    network = build_network(discovery)
    stats = network.get_network_stats()
    print(f"✅ 节点加入完成：{network.network_id} 共 {stats['total_nodes']} 个节点\n")

    print("按能力匹配建立连接：")
    for left, right, shared in connect_by_capability(network, discovery):
        print(f"  {left} <-> {right}（共同能力：{', '.join(shared)}）")

    best = select_best_service(find_services(discovery, service_type="nlp"))
    if connect(network, "router_agent", best.service_id):
        print(f"  router_agent -> {best.service_id}（按负载选出的 NLP 服务）")

    try:
        connect(network, "nlp_agent_1", "vision_agent")
    except KeyError as exc:
        print(f"  连接 vision_agent 失败：{exc}")

    print("\n当前拓扑：")
    print_edges(network)

    stats = network.get_network_stats()
    print(
        f"\n📊 网络统计：节点 {stats['total_nodes']} 个"
        f"（活跃 {stats['active_nodes']}），连接 {stats['total_connections']} 条"
    )

    print("\n消息路由：")
    for source, target in (
        ("router_agent", "nlp_agent_1"),
        ("router_agent", "nlp_agent_2"),
        ("router_agent", "vision_agent"),
    ):
        path = network.route_message(source, target, {"type": "task", "content": "分析这段文本"})
        print(f"  {source} → {target}：{' -> '.join(path) if path else '无可用路径'}")

    recipients = network.broadcast_message("nlp_agent_1", {"type": "notify", "content": "开始批量任务"})
    print(f"\n📢 广播：nlp_agent_1 → {', '.join(recipients) or '无接收者'}")


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    demo()
