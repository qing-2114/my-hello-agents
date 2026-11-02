"""第十章：SSE（Server-Sent Events）传输示例。

项目来源：https://hello-agents.datawhale.cc/
对应教程第十章「传输方式」中 SSE 传输示例代码，使用项目根目录 .conda 环境。
MCPTool 主要用于 Stdio 和 Memory 传输；SSE 传输使用底层的 MCPClient。

教程连接的 http://localhost:8080/sse 需要自备服务器。本脚本会先在后台启动本机的 sse_mcp_server.py，
再通过 SSE 连接它，结束时关闭服务器。
"""

import asyncio
import subprocess
import sys
from pathlib import Path

# Windows 控制台默认 GBK，hello-agents/fastmcp 打印的 emoji 会导致 MCP 调用失败
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from hello_agents.protocols import MCPClient

from mcp_http_transport_demo import wait_for_port

HOST = "127.0.0.1"
PORT = 8767
SERVER_URL = f"http://{HOST}:{PORT}/sse"
SERVER_SCRIPT = Path(__file__).resolve().parent / "sse_mcp_server.py"


async def test_sse_transport():
    # 连接到 SSE MCP 服务器（必须显式指定 transport_type="sse"，否则 http:// 开头的 URL 默认走 Streamable HTTP）
    client = MCPClient(SERVER_URL, transport_type="sse")

    async with client:
        # SSE 特别适合流式处理
        result = await client.call_tool("stream_process", {
            "input": "大量数据处理请求",
            "stream": True
        })
        print(f"流式处理结果: {result}")


async def show_progress(progress: float, total: float | None, message: str | None) -> None:
    print(f"  ⏳ 进度 {progress:.0f}/{total:.0f}：{message}")


async def test_sse_progress():
    # hello-agents 的 call_tool 只返回最终结果，看不到中间推送；
    # 这里改用底层 fastmcp 客户端 client.client，传入 progress_handler 接收服务器推送的进度
    client = MCPClient(SERVER_URL, transport_type="sse")

    async with client:
        result = await client.client.call_tool(
            "stream_process",
            {"input": "大量数据处理请求", "stream": True},
            progress_handler=show_progress,
        )
        print(f"流式处理结果: {result.content[0].text}")


def main():
    server = subprocess.Popen([sys.executable, str(SERVER_SCRIPT), str(PORT)])
    try:
        wait_for_port(HOST, PORT)
        print(f"SSE MCP 服务器已启动：{SERVER_URL}")

        print("\n=== 教程写法：只拿最终结果 ===")
        asyncio.run(test_sse_transport())

        print("\n=== 接收服务器推送的进度 ===")
        asyncio.run(test_sse_progress())
    finally:
        server.terminate()
        server.wait(timeout=10)
        print("\nSSE MCP 服务器已关闭")


if __name__ == "__main__":
    main()
