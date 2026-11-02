"""第十章：以 Streamable HTTP 传输运行的 MCP 服务器，供 mcp_http_transport_demo.py 连接。

项目来源：https://hello-agents.datawhale.cc/
教程示例连接的 http://api.example.com/mcp 并不存在，这里在本机提供一个等价的服务器。
单独运行：python http_mcp_server.py [端口]，默认监听 http://127.0.0.1:8765/mcp
"""

import sys

from fastmcp import FastMCP

mcp = FastMCP("http-demo-server")

OPERATIONS = {
    "uppercase": str.upper,
    "lowercase": str.lower,
    "reverse": lambda s: s[::-1],
}


@mcp.tool()
def process_data(data: str, operation: str) -> str:
    """处理文本数据，operation 可选 uppercase / lowercase / reverse"""
    if operation not in OPERATIONS:
        raise ValueError(f"不支持的操作 '{operation}'，可选：{', '.join(OPERATIONS)}")
    return OPERATIONS[operation](data)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    # 只监听本机回环地址；transport="http" 即 Streamable HTTP，默认路径为 /mcp
    mcp.run(transport="http", host="127.0.0.1", port=port, show_banner=False)
