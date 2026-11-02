"""ANP 服务发现：注册服务，再按类型、能力、元数据查找并挑选最优服务。

项目来源：https://hello-agents.datawhale.cc/
本示例只操作内存中的服务注册表，不启动 endpoint 对应的 HTTP 服务，也不调用 LLM。
"""

import sys
from typing import Any, List, Optional

from hello_agents.protocols import (
    ANPDiscovery,
    ServiceInfo,
    discover_service,
    register_service,
)

# 示例约定的归一化负载（0~1）；实际应用需自行采集和更新。
DEFAULT_LOAD = 1.0


def create_discovery() -> ANPDiscovery:
    """创建包含四个 Agent 的内存服务发现中心。"""
    discovery = ANPDiscovery()

    register_service(
        discovery=discovery,
        service_id="nlp_agent_1",
        service_name="NLP处理专家A",
        service_type="nlp",
        capabilities=["text_analysis", "sentiment_analysis", "ner"],
        endpoint="http://localhost:8001",
        metadata={"load": 0.3, "price": 0.01, "version": "1.0.0"},
    )

    register_service(
        discovery=discovery,
        service_id="nlp_agent_2",
        service_name="NLP处理专家B",
        service_type="nlp",
        capabilities=["text_analysis", "translation"],
        endpoint="http://localhost:8002",
        metadata={"load": 0.7, "price": 0.02, "version": "1.1.0"},
    )

    register_service(
        discovery=discovery,
        service_id="translate_agent",
        service_name="翻译专家",
        service_type="translation",
        capabilities=["translation", "text_analysis"],
        endpoint="http://localhost:8003",
        metadata={"load": 0.5, "price": 0.03, "version": "2.0.0"},
    )

    register_service(
        discovery=discovery,
        service_id="router_agent",
        service_name="任务路由器",
        service_type="router",
        capabilities=["routing", "task_dispatch"],
        endpoint="http://localhost:8000",
        metadata={"load": 0.1, "price": 0.0, "version": "1.0.0"},
    )

    return discovery


def find_services(
    discovery: ANPDiscovery,
    service_type: Optional[str] = None,
    capability: Optional[str] = None,
    **metadata_filters: Any,
) -> List[ServiceInfo]:
    """按类型、能力、元数据组合查找服务。

    库的 ``discover_service()`` 只接收 service_type；``discover_services()`` 的
    filters 也只是对 metadata 做全等比较，因此 capability 需要在这层再筛一次。
    """
    services = discover_service(discovery, service_type=service_type)
    if capability:
        services = [s for s in services if capability in s.capabilities]
    if metadata_filters:
        services = [
            s
            for s in services
            if all(s.metadata.get(key) == value for key, value in metadata_filters.items())
        ]
    return services


def _as_number(value: Any, default: float) -> float:
    """把元数据里的数值转成 float，缺失或类型不对时回退到默认值。"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    return float(value)


def service_score(service: ServiceInfo) -> tuple:
    """排序键：负载越低越优，负载相同时价格越低越优。

    教程写法 ``s.metadata.get("load", 1.0)`` 把缺失负载当作最大负载处理，
    这里沿用该约定，并额外处理 ``"0.3"`` 这类非数值字符串。
    """
    load = _as_number(service.metadata.get("load"), DEFAULT_LOAD)
    price = _as_number(service.metadata.get("price"), 0.0)
    return (load, price)


def select_best_service(services: List[ServiceInfo]) -> Optional[ServiceInfo]:
    """挑选当前负载最低的服务；候选为空时返回 None。"""
    services = list(services)
    if not services:
        return None
    return min(services, key=service_score)


def print_services(title: str, services: List[ServiceInfo]) -> None:
    print(f"{title}：{len(services)} 个")
    for service in services:
        load = service.metadata.get("load", "未上报")
        print(
            f"  - {service.service_id:<14} {service.service_name}"
            f"  类型={service.service_type}  负载={load}"
            f"  能力={','.join(service.capabilities)}"
        )


def demo() -> None:
    discovery = create_discovery()
    print(f"✅ 服务注册完成，共 {len(discovery.list_all_services())} 个服务\n")

    print_services("全部服务", discovery.list_all_services())

    nlp_services = find_services(discovery, service_type="nlp")
    print()
    print_services("按类型 nlp 查找", nlp_services)
    best = select_best_service(nlp_services)
    print(f"最佳 NLP 服务：{best.service_name}（负载 {best.metadata['load']}）")

    print()
    print_services("按能力 translation 查找", find_services(discovery, capability="translation"))
    print_services(
        "按版本 1.1.0 查找",
        find_services(discovery, version="1.1.0"),
    )

    empty = find_services(discovery, service_type="vision")
    print(f"\n按类型 vision 查找：{len(empty)} 个，最佳服务：{select_best_service(empty)}")


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    demo()
