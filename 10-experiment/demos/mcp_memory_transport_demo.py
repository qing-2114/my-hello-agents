"""第十章：Memory（内存）传输示例。

项目来源：https://hello-agents.datawhale.cc/
对应教程第十章「传输方式」中 Memory 传输示例代码，使用项目根目录 .conda 环境。
内存传输时客户端与服务器在同一个 Python 进程内，不启动子进程、不走网络，适合单元测试和快速原型。
"""

import asyncio
import sys

# Windows 控制台默认 GBK，hello-agents/fastmcp 打印的 emoji 会导致 MCP 调用失败
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from hello_agents.protocols import MCPClient
from hello_agents.tools import MCPTool

# 同目录下的自定义服务器；导入时 __main__ 分支不会执行，只拿到 FastMCP 实例
from my_mcp_server import mcp as my_server


def builtin_server_demo():
    # 使用内置演示服务器（Memory传输）
    mcp_tool = MCPTool()

    # 列出可用工具
    result = mcp_tool.run({"action": "list_tools"})
    print(result)

    # 调用工具
    result = mcp_tool.run({
        "action": "call_tool",
        "tool_name": "add",
        "arguments": {"a": 10, "b": 20}
    })
    print(result)


async def custom_server_demo():
    # 把 FastMCP 实例直接传给 MCPClient 即为内存传输（stdio 方式传的是启动命令）
    async with MCPClient(my_server) as client:
        tools = await client.list_tools()
        print(f"可用工具: {[t['name'] for t in tools]}")

        result = await client.call_tool("add", {"a": 1.5, "b": 2.5})
        print(f"add(1.5, 2.5) = {result}")


if __name__ == "__main__":
    print("=== 内置演示服务器（同步 MCPTool） ===")
    builtin_server_demo()

    print("\n=== 自定义服务器实例（异步 MCPClient） ===")
    asyncio.run(custom_server_demo())
