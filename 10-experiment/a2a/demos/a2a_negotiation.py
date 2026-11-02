"""A2A 规则协商：提案 → 反提案 → 确认或终止。

项目来源：https://hello-agents.datawhale.cc/
使用 hello-agents 的 HTTP 封装，不调用 LLM；协商策略由业务规则决定。
"""

import argparse
import json
import re
import socket
import sys
import threading
import time

import requests
from hello_agents.protocols import A2AClient, A2AServer

HOST = "127.0.0.1"


def encode(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False)


def positive_int(value, name: str) -> int:
    if type(value) is not int or value < 1:
        raise ValueError(f"{name} 必须是正整数")
    return value


def parse_request(text: str, command: str) -> dict:
    """推荐 JSON；兼容 negotiate task:任务 deadline:3 的教程输入。"""
    text = re.sub(rf"^\s*{command}\s+", "", text, count=1, flags=re.IGNORECASE).strip()
    if command == "negotiate" and not text.startswith("{"):
        match = re.fullmatch(r"task:(.+?)\s+deadline:(\d+)", text, re.IGNORECASE | re.DOTALL)
        if not match:
            raise ValueError("请使用 JSON 或 negotiate task:任务 deadline:天数")
        data = {"task": match[1].strip(), "deadline": int(match[2])}
    else:
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            raise ValueError("提案必须是合法 JSON，不接受 Python 字典字符串或表达式") from None
    if not isinstance(data, dict):
        raise ValueError("请求必须是 JSON 对象")
    task = data.get("task")
    if not isinstance(task, str) or not task.strip():
        raise ValueError("task 必须是非空字符串")
    data["task"] = task.strip()
    positive_int(data.get("deadline"), "deadline")
    return data


def call_json(client: A2AClient, skill: str, data: dict) -> dict:
    """检查 HTTP 技能执行结果，不将通信失败视为业务拒绝。"""
    envelope = client.execute_skill(skill, encode(data))
    if envelope.get("status") != "success":
        raise RuntimeError(f"{skill} 服务调用失败，请检查对方服务和网络")
    try:
        result = json.loads(envelope["result"])
    except (KeyError, TypeError, json.JSONDecodeError):
        raise RuntimeError("对方返回了无效 JSON") from None
    if not isinstance(result, dict):
        raise RuntimeError("对方返回的结果不是 JSON 对象")
    return result


def create_agents(agent1_url: str, min_days: int = 7) -> tuple[A2AServer, A2AServer]:
    positive_int(min_days, "min_days")
    agent1 = A2AServer(name="agent1", description=f"任务执行方，至少需要 {min_days} 天")
    agent2 = A2AServer(name="agent2", description="任务委托方，在期限预算内处理反提案")

    @agent1.skill("propose")
    def handle_proposal(text: str) -> str:
        try:
            proposal = parse_request(text, "propose")
        except ValueError as exc:
            return encode({"status": "error", "accepted": False, "message": str(exc)})
        if proposal["deadline"] >= min_days:
            return encode({
                "status": "accepted", "accepted": True, "message": "接受提案",
                "agreement": {"task": proposal["task"], "deadline": proposal["deadline"]},
            })
        return encode({
            "status": "counter_proposal", "accepted": False, "message": "时间太紧",
            "counter_proposal": {"deadline": min_days},
        })

    @agent2.skill("negotiate")
    def negotiate_task(text: str) -> str:
        history = []
        try:
            request = parse_request(text, "negotiate")
            deadline = request["deadline"]
            max_deadline = positive_int(request.get("max_deadline", max(deadline, 7)), "max_deadline")
            max_rounds = positive_int(request.get("max_rounds", 3), "max_rounds")
            if max_rounds > 10:
                raise ValueError("max_rounds 不能超过 10")
            if max_deadline < deadline:
                raise ValueError("max_deadline 不能小于首次提案的 deadline")
            client = A2AClient(agent1_url)
            for round_number in range(1, max_rounds + 1):
                proposal = {"task": request["task"], "deadline": deadline}
                reply = call_json(client, "propose", proposal)
                history.append({"round": round_number, "proposal": proposal, "reply": reply})
                if reply.get("status") == "accepted" and reply.get("accepted") is True:
                    if reply.get("agreement") != proposal:
                        raise RuntimeError("对方确认的条款与当前提案不一致")
                    return encode({
                        "status": "agreed", "message": "双方已确认提案", "agreement": proposal,
                        "rounds": round_number, "history": history,
                    })
                if reply.get("status") != "counter_proposal" or reply.get("accepted") is not False:
                    raise RuntimeError("对方未返回有效的接受或反提案结果")
                counter = reply.get("counter_proposal")
                if not isinstance(counter, dict):
                    raise RuntimeError("反提案格式错误")
                next_deadline = positive_int(counter.get("deadline"), "反提案 deadline")
                if next_deadline > max_deadline:
                    return encode({
                        "status": "rejected", "message": "反提案超过委托方可接受的最长期限",
                        "max_deadline": max_deadline, "rounds": round_number, "history": history,
                    })
                if next_deadline <= deadline:
                    raise RuntimeError("反提案没有推进协商，已终止")
                deadline = next_deadline
            return encode({
                "status": "max_rounds", "message": "达到轮数上限，尚未达成协议",
                "rounds": len(history), "history": history,
            })
        except (ValueError, RuntimeError) as exc:
            return encode({"status": "error", "message": str(exc), "rounds": len(history), "history": history})

    return agent1, agent2


def start_agents(agents: tuple[A2AServer, A2AServer], ports: tuple[int, int]) -> None:
    if len(set(ports)) != 2 or any(type(p) is not int or not 1 <= p <= 65535 for p in ports):
        raise ValueError("两个端口必须不同，且在 1–65535 范围内")
    # 同时保留两个探测 socket，确保检查全部端口后再启动服务。
    with socket.socket() as first, socket.socket() as second:
        for probe, port in zip((first, second), ports):
            try:
                probe.bind((HOST, port))
            except OSError:
                raise RuntimeError(f"端口 {port} 不可用") from None
    for agent, port in zip(agents, ports):
        threading.Thread(target=agent.run, kwargs={"host": HOST, "port": port}, daemon=True).start()
    end = time.monotonic() + 10
    for agent, port in zip(agents, ports):
        while time.monotonic() < end:
            try:
                response = requests.get(f"http://{HOST}:{port}/health", timeout=0.5)
                if response.ok and response.json().get("agent") == agent.name:
                    break
            except (requests.RequestException, ValueError):
                pass
            time.sleep(0.1)
        else:
            raise RuntimeError(f"{agent.name} 启动失败")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", default="开发智能客服系统")
    parser.add_argument("--deadline", type=int, default=3, help="首次提案的工期，单位天")
    parser.add_argument("--max-deadline", type=int, default=10, help="委托方能接受的最长工期")
    parser.add_argument("--min-days", type=int, default=7, help="执行方至少需要的天数")
    parser.add_argument("--max-rounds", type=int, default=3)
    parser.add_argument("--port1", type=int, default=7000)
    parser.add_argument("--port2", type=int, default=7001)
    args = parser.parse_args()
    try:
        agents = create_agents(f"http://{HOST}:{args.port1}", args.min_days)
        start_agents(agents, (args.port1, args.port2))
        # 客户端 → Agent 2 → Agent 1；反提案须重新发给 Agent 1 确认。
        result = call_json(A2AClient(f"http://{HOST}:{args.port2}"), "negotiate", {
            "task": args.task, "deadline": args.deadline,
            "max_deadline": args.max_deadline, "max_rounds": args.max_rounds,
        })
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["status"] == "agreed" else 1
    except (ValueError, RuntimeError) as exc:
        print(f"协商失败：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
