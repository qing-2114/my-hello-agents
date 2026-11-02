"""第十章：创建 A2A 客户端，与计算器智能体服务端通信。

项目来源：https://hello-agents.datawhale.cc/
对应教程第十章「客户端调用」示例。教程原代码连接的是研究员 Agent 的 research 技能，
这里改为连接本项目的 calculator-agent。

运行前先在另一个终端启动服务端：
    .\\.conda\\python.exe -X utf8 10-experiment\\a2a\\demos\\a2a_calculator_agent.py --serve
"""

import sys

# Windows 控制台默认 GBK，打印 emoji 会报 UnicodeEncodeError
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from hello_agents.protocols import A2AClient

SERVER_URL = "http://localhost:5000"


def main():
    # 创建客户端连接到计算器 Agent
    client = A2AClient(SERVER_URL)

    # 1. 获取 Agent 信息（GET /info）
    info = client.get_info()
    if "error" in info:
        print(f"❌ 无法连接服务端 {SERVER_URL}: {info['error']}")
        print("💡 请先运行: python a2a_calculator_agent.py --serve")
        return
    print(f"🤖 已连接: {info['name']} v{info['version']} - {info['description']}")

    # 2. 列出技能（GET /skills）
    print(f"🛠️  可用技能: {client.list_skills()}")

    # 3. 执行指定技能（POST /execute/<skill>）
    print("\n🧪 执行技能:")
    requests_to_send = [
        ("add", "计算 10 + 5"),
        ("add", "计算 2 加上 3"),
        ("multiply", "计算 4 乘以 2.5"),
        ("info", "获取信息"),
        ("divide", "计算 8 / 2"),  # 服务端未注册，演示 404 错误分支
    ]
    for skill, text in requests_to_send:
        response = client.execute_skill(skill, text)
        if response.get("status") == "success":
            print(f"  ✅ [{skill}] {text} -> {response.get('result')}")
        else:
            print(f"  ❌ [{skill}] {text} -> {response.get('error')}")

    # 4. 通用问答（POST /ask）：服务端按注册顺序依次尝试技能，返回第一个非 Error 开头的结果
    print("\n💬 通用问答:")
    question = "计算 1 + 2 + 3"
    print(f"  ❓ {question}")
    print(f"  🤖 {client.ask(question)}")


if __name__ == "__main__":
    main()
