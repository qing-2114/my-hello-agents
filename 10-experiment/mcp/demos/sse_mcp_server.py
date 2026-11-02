"""第十章：以 SSE 传输运行的 MCP 服务器，供 mcp_sse_transport_demo.py 连接。

项目来源：https://hello-agents.datawhale.cc/
教程示例连接的 http://localhost:8080/sse 需要自备服务器，这里在本机提供一个等价的服务器。
单独运行：python sse_mcp_server.py [端口]，默认监听 http://127.0.0.1:8767/sse
注意：SSE 是 MCP 早期的远程传输方式，已被 Streamable HTTP 取代，仅为兼容旧服务器保留。
"""

import asyncio
import sys

from fastmcp import Context, FastMCP

mcp = FastMCP("sse-demo-server")


@mcp.tool()
async def stream_process(input: str, stream: bool, ctx: Context) -> str:
    """分块处理文本；stream 为 True 时每处理完一块就向客户端推送一次进度"""
    chunks = [input[i:i + 2] for i in range(0, len(input), 2)]
    processed = []
    for i, chunk in enumerate(chunks, start=1):
        await asyncio.sleep(0.3)  # 模拟耗时处理
        processed.append(f"[{chunk}]")
        if stream:
            # 进度通知通过 SSE 连接由服务器主动推送给客户端
            await ctx.report_progress(i, len(chunks), f"已处理第 {i} 块：{chunk}")
    return f"处理完成，共 {len(chunks)} 块：{''.join(processed)}"


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8767
    # 只监听本机回环地址；transport="sse" 时默认路径为 /sse
    mcp.run(transport="sse", host="127.0.0.1", port=port, show_banner=False)
