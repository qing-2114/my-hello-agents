"""第十章：MCP / A2A / ANP 三种协议的基本功能体验。

项目来源：https://hello-agents.datawhale.cc/
对应教程第十章示例代码，使用项目根目录 .conda 环境（hello-agents[protocols]==0.2.8）。
"""

import sys

# Windows 控制台默认 GBK，hello-agents/fastmcp 打印的 emoji 会导致 MCP 调用失败
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from hello_agents.tools import MCPTool, A2ATool, ANPTool

# 1. MCP：访问工具（不传 server_command 时使用内置的内存 MCP 服务器）
mcp_tool = MCPTool()
result = mcp_tool.run({
    "action": "call_tool",
    "tool_name": "add",
    "arguments": {"a": 10, "b": 20}
})
print(f"MCP计算结果: {result}")  # 输出: 30.0

# 2. ANP：服务发现
anp_tool = ANPTool()
anp_tool.run({
    "action": "register_service",
    "service_id": "calculator",
    "service_type": "math",
    "endpoint": "http://localhost:8080"
})
services = anp_tool.run({"action": "discover_services"})
print(f"发现的服务: {services}")

# 3. A2A：智能体通信（这里只创建客户端，不连接；5000 端口无需有服务在运行）
a2a_tool = A2ATool("http://localhost:5000")
print("A2A工具创建成功")
