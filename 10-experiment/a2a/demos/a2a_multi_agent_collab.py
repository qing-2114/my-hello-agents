"""第十章：多个 A2A 智能体协作（研究员 → 撰写员 → 编辑）。

项目来源：https://hello-agents.datawhale.cc/
对应教程第十章多 Agent 协作示例。一个进程内用线程启动 3 个 A2AServer，
再分别创建 3 个 A2AClient，按「研究 → 撰写 → 编辑」顺序串联调用。
本示例不调用 LLM。

相对教程原代码的修正：
- 用 ast.literal_eval 代替 eval：eval 会执行收到的任意字符串，属于代码注入风险。
- 正则加 re.DOTALL：文章是多行文本，原写法 (.+) 不匹配换行，编辑员只能拿到第一行标题。
- 用 /health 轮询代替固定 time.sleep(2)，并只监听 127.0.0.1（A2AServer 没有鉴权）。
- 端口改为 5001-5003，避免和计算器服务端（5000）冲突；启动前检查端口占用，
  轮询时校验 Agent 名称，防止请求落到其他服务上。
"""

import ast
import re
import socket
import sys
import threading
import time

# Windows 控制台默认 GBK，打印 emoji 会报 UnicodeEncodeError
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

import requests
from hello_agents.protocols import A2AServer, A2AClient

HOST = "127.0.0.1"

# 1. 创建多个 Agent 服务
researcher = A2AServer(name="researcher", description="研究员")


@researcher.skill("research")
def do_research(text: str) -> str:
    match = re.search(r"research\s+(.+)", text, re.IGNORECASE | re.DOTALL)
    topic = match.group(1).strip() if match else text
    return str({"topic": topic, "findings": f"{topic}的研究结果"})


writer = A2AServer(name="writer", description="撰写员")


@writer.skill("write")
def write_article(text: str) -> str:
    match = re.search(r"write\s+(.+)", text, re.IGNORECASE | re.DOTALL)
    content = match.group(1).strip() if match else text

    # 尝试解析研究员返回的字典字符串；literal_eval 只接受字面量，不会执行代码
    try:
        data = ast.literal_eval(content)
        topic = data.get("topic", "未知主题")
        findings = data.get("findings", "无研究结果")
    except (ValueError, SyntaxError, AttributeError):
        topic = "未知主题"
        findings = content

    return f"# {topic}\n\n基于研究：{findings}\n\n文章内容..."


editor = A2AServer(name="editor", description="编辑")


@editor.skill("edit")
def edit_article(text: str) -> str:
    match = re.search(r"edit\s+(.+)", text, re.IGNORECASE | re.DOTALL)
    article = match.group(1).strip() if match else text

    result = {
        "article": article + "\n\n[已编辑优化]",
        "feedback": "文章质量良好",
        "approved": True,
    }
    return str(result)


def port_in_use(port: int) -> bool:
    """检查端口是否已有服务在监听。
    Windows 上端口被占用时 Flask 线程可能不报错，请求会落到旧服务上，所以要提前检查。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((HOST, port)) == 0


def wait_until_healthy(url: str, expected_name: str, timeout: float = 10.0) -> bool:
    """轮询 /health，确认响应的是预期的 Agent 后返回"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            resp = requests.get(f"{url}/health", timeout=1)
            if resp.ok and resp.json().get("agent") == expected_name:
                return True
        except requests.RequestException:
            pass
        time.sleep(0.2)
    return False


def call_skill(client: A2AClient, skill: str, text: str) -> str:
    """调用技能并取出 result；失败时直接抛错，避免把错误信息当成正常数据传给下一个 Agent"""
    response = client.execute_skill(skill, text)
    if response.get("status") != "success":
        raise RuntimeError(f"{skill} 调用失败: {response.get('error')}")
    return response.get("result", "")


# 4. 协作流程
def create_content(topic, researcher_client, writer_client, editor_client):
    # 步骤1：研究
    research_data = call_skill(researcher_client, "research", f"research {topic}")
    print(f"🔎 研究员 → {research_data}")

    # 步骤2：撰写
    article_content = call_skill(writer_client, "write", f"write {research_data}")
    print(f"✍️  撰写员 → {article_content!r}")

    # 步骤3：编辑
    return call_skill(editor_client, "edit", f"edit {article_content}")


if __name__ == "__main__":
    # 端口避开 5000，那是 a2a_calculator_agent.py --serve 使用的端口
    agents = [(researcher, 5001), (writer, 5002), (editor, 5003)]

    busy = [port for _, port in agents if port_in_use(port)]
    if busy:
        print(f"❌ 端口 {busy} 已被占用，请先关闭占用的进程")
        sys.exit(1)

    # 2. 启动所有服务（daemon 线程，主线程结束时随之退出）
    for agent, port in agents:
        threading.Thread(
            target=lambda a=agent, p=port: a.run(host=HOST, port=p), daemon=True
        ).start()

    urls = [f"http://{HOST}:{port}" for _, port in agents]
    if not all(wait_until_healthy(url, agent.name) for url, (agent, _) in zip(urls, agents)):
        print("❌ 有服务未能在 10 秒内启动")
        sys.exit(1)

    # 3. 创建客户端连接到各个 Agent
    researcher_client, writer_client, editor_client = (A2AClient(url) for url in urls)
    for client in (researcher_client, writer_client, editor_client):
        info = client.get_info()
        print(f"🤝 已连接 {client.server_url}: {info['name']}（{info['description']}），技能 {info['skills']}")
    print()

    result = create_content("AI在医疗领域的应用", researcher_client, writer_client, editor_client)

    # 编辑员返回的也是字典字符串，解析后分字段打印
    final = ast.literal_eval(result)
    print(f"\n📝 最终结果：\n{final['article']}")
    print(f"\n💬 反馈：{final['feedback']}，通过：{final['approved']}")
