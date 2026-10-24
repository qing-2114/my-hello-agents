"""第十章：HTTP（Streamable HTTP）传输示例。

项目来源：https://hello-agents.datawhale.cc/
对应教程第十章「传输方式」中 HTTP 传输示例代码，使用项目根目录 .conda 环境。
MCPTool 主要用于 Stdio 和 Memory 传输；HTTP/SSE 等远程传输使用底层的 MCPClient。

教程连接的 http://api.example.com/mcp 并不存在。本脚本会先在后台启动本机的 http_mcp_server.py，
再通过 HTTP 连接它，结束时关闭服务器。与 stdio 不同，HTTP 服务器是独立运行的服务，
客户端只按 URL 连接，不负责启动它；这里自动启动只是为了让示例开箱即用。
"""

import asyncio
import socket
import subprocess
import sys
import time
from pathlib import Path

# Windows 控制台默认 GBK，hello-agents/fastmcp 打印的 emoji 会导致 MCP 调用失败
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from hello_agents.protocols import MCPClient

HOST = "127.0.0.1"
PORT = 8765
SERVER_URL = f"http://{HOST}:{PORT}/mcp"
SERVER_SCRIPT = Path(__file__).resolve().parent / "http_mcp_server.py"


async def test_http_transport():
    # 连接到远程 HTTP MCP 服务器（URL 以 http:// 开头时，MCPClient 默认使用 Streamable HTTP 传输）
    client = MCPClient(SERVER_URL)

    async with client:
        # 获取服务器信息
        tools = await client.list_tools()
        print(f"远程服务器工具: {len(tools)} 个 {[t['name'] for t in tools]}")

        # 调用远程工具
        result = await client.call_tool("process_data", {
            "data": "Hello, World!",
            "operation": "uppercase"
        })
        print(f"远程处理结果: {result}")


def wait_for_port(host: str, port: int, timeout: float = 30) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1):
                return
        except OSError:
            time.sleep(0.3)
    raise TimeoutError(f"HTTP MCP 服务器在 {timeout} 秒内未启动：{host}:{port}")


def main():
    server = subprocess.Popen([sys.executable, str(SERVER_SCRIPT), str(PORT)])
    try:
        wait_for_port(HOST, PORT)
        print(f"HTTP MCP 服务器已启动：{SERVER_URL}")
        asyncio.run(test_http_transport())
    finally:
        server.terminate()
        server.wait(timeout=10)
        print("HTTP MCP 服务器已关闭")


if __name__ == "__main__":
    main()
