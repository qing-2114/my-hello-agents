"""ANP + 真实 LLM 的计算节点推荐。端点为示例，不执行远程任务。

项目来源：https://hello-agents.datawhale.cc/
"""

import argparse
import json
from pathlib import Path
import random

from dotenv import dotenv_values
from hello_agents import HelloAgentsLLM, SimpleAgent
from hello_agents.protocols import ANPDiscovery, register_service
from hello_agents.tools.builtin import ANPTool

ROOT = Path(__file__).resolve().parents[3]
DEMO_TASKS = (
    ("训练一个大型深度学习模型，需要GPU支持", True),
    ("处理大量文本数据，需要高内存", False),
    ("运行轻量级数据分析任务", False),
)


def create_discovery(seed: int = 42) -> ANPDiscovery:
    rng = random.Random(seed)
    discovery = ANPDiscovery()
    for i in range(10):
        register_service(
            discovery=discovery, service_id=f"compute_node_{i}",
            service_name=f"计算节点{i}", service_type="compute",
            capabilities=["data_processing", "ml_training"],
            endpoint=f"http://node{i}:8000",
            metadata={"load": round(rng.uniform(0.1, 0.9), 3),
                      "cpu_cores": rng.choice([4, 8, 16]),
                      "memory_gb": rng.choice([16, 32, 64]),
                      "gpu": rng.choice([True, False])},
        )
    return discovery


class DiscoveryTool(ANPTool):
    """只开放发现操作，并记录模型实际查询，避免模型改写注册表。"""

    def __init__(self, discovery):
        super().__init__(name="service_discovery", discovery=discovery,
                         description="查询计算节点及负载、CPU、内存和GPU。仅支持 discover_services。")
        self.calls = []

    def run(self, parameters):
        if parameters.get("action") != "discover_services":
            return "错误：本工具只允许 discover_services"
        result = super().run(parameters)
        self.calls.append({"parameters": dict(parameters), "result": result})
        return result


def load_llm() -> HelloAgentsLLM:
    path = ROOT / ".env"
    config = dotenv_values(path) if path.is_file() else {}
    missing = [k for k in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL_ID") if not config.get(k)]
    if missing:
        raise ValueError("根目录 .env 缺少配置：" + "、".join(missing))
    return HelloAgentsLLM(provider="custom", api_key=config["LLM_API_KEY"],
                          base_url=config["LLM_BASE_URL"], model=config["LLM_MODEL_ID"],
                          temperature=0.2, timeout=60)


def create_scheduler(discovery, llm):
    scheduler = SimpleAgent(
        name="任务调度器", llm=llm,
        system_prompt="""你是智能任务调度器。必须先调用 service_discovery，使用
action=discover_services、service_type=compute，读取全部节点后再选择。
逐个分析负载、CPU、内存、GPU；GPU要求是硬约束，高内存任务优先内存，
轻量任务兼顾低负载和资源节约。不虚构资源，不声称任务已执行。
最终只输出JSON对象：{"nodes":[{"service_id":"节点ID","analysis":"节点分析"}],
"selected_node":"节点ID或null（无满足条件节点）","reason":"选择或拒绝理由"}。
nodes必须列出所有发现的计算节点，即使不满足任务要求。""",
    )
    tool = DiscoveryTool(discovery)
    scheduler.add_tool(tool)
    return scheduler, tool


def assign_task(scheduler, tool, discovery, task_description, requires_gpu=False):
    if not task_description.strip():
        raise ValueError("任务描述不能为空")
    scheduler.clear_history()
    tool.calls.clear()
    prompt = (
        f"请为任务选择最合适节点：{task_description}\nGPU硬约束：{requires_gpu}。"
        "列出所有节点并逐个分析，给出选择及理由。只推荐，不执行任务。"
    )
    services = {s.service_id: s for s in discovery.list_all_services() if s.service_type == "compute"}
    eligible = {k for k, s in services.items() if not requires_gpu or s.metadata.get("gpu") is True}
    errors = []
    for attempt in range(2):
        response = scheduler.run(prompt if attempt == 0 else
                                 prompt + "\n上次输出格式无效：" + errors[-1] +
                                 "。请严格输出有效JSON，不要Markdown代码围栏。")
        if not any(c["parameters"].get("service_type") == "compute" for c in tool.calls):
            errors.append("未实际调用节点发现工具")
            continue
        try:
            raw = response.strip()
            if raw.startswith("```") and raw.endswith("```"):
                raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            result = json.loads(raw)
            rows = result["nodes"]
            if (len(rows) != len(services) or {r["service_id"] for r in rows} != set(services)
                    or not all(isinstance(r.get("analysis"), str) and r["analysis"].strip() for r in rows)):
                raise ValueError("节点分析缺失或包含虚构节点")
            selected = result["selected_node"]
            if (selected is None and eligible) or (selected is not None and selected not in eligible):
                raise ValueError("所选节点不存在、不满足GPU约束，或错误拒绝可用节点")
            if not isinstance(result.get("reason"), str) or not result["reason"].strip():
                raise ValueError("缺少选择理由")
            return result
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            errors.append(str(exc))
    raise ValueError("模型两次输出均未通过调度结果校验：" + errors[-1])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--task", help="单个自定义任务")
    parser.add_argument("--requires-gpu", action="store_true", help="自定义任务的GPU硬约束")
    args = parser.parse_args()
    discovery = create_discovery(args.seed)
    scheduler, tool = create_scheduler(discovery, load_llm())
    print(f"已注册 {len(discovery.list_all_services())} 个节点（仅推荐，不远程执行）")
    tasks = [(args.task, args.requires_gpu)] if args.task else DEMO_TASKS
    for description, gpu in tasks:
        result = assign_task(scheduler, tool, discovery, description, gpu)
        print(f"\n任务：{description}")
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
