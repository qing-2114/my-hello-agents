"""第十章：Stdio（标准输入输出）传输示例。

项目来源：https://hello-agents.datawhale.cc/
对应教程第十章「传输方式」中 Stdio 传输示例代码，使用项目根目录 .conda 环境。
Stdio 传输由客户端把服务器作为子进程启动，通过 stdin/stdout 收发消息；方式2 依赖 Node.js（npx）。
"""

import sys
from pathlib import Path

# Windows 控制台默认 GBK，hello-agents/fastmcp 打印的 emoji 会导致 MCP 调用失败
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from hello_agents.tools import MCPTool

DEMOS_DIR = Path(__file__).resolve().parent
# 教程写的是相对路径 "my_mcp_server.py" 和 "."，结果依赖运行时工作目录，这里固定为绝对路径
CUSTOM_SERVER = str(DEMOS_DIR / "my_mcp_server.py")
FS_ROOT = str(DEMOS_DIR.parent)


def custom_server_demo():
    # 方式1：使用自定义Python服务器
    mcp_tool = MCPTool(name="my_server", server_command=["python", CUSTOM_SERVER])

    # 列出工具
    result = mcp_tool.run({"action": "list_tools"})
    print(result)

    # 调用工具（自定义服务器只有 add 工具）
    result = mcp_tool.run({
        "action": "call_tool",
        "tool_name": "add",
        "arguments": {"a": 10, "b": 20}
    })
    print(result)


def filesystem_server_demo():
    # 方式2：使用社区服务器（文件系统）
    mcp_tool = MCPTool(
        name="filesystem",
        server_command=["npx", "-y", "@modelcontextprotocol/server-filesystem", FS_ROOT]
    )

    # 列出工具
    result = mcp_tool.run({"action": "list_tools"})
    print(result)

    # 调用工具（相对路径由服务器按允许目录 FS_ROOT 解析；只读前 5 行，避免输出过长）
    result = mcp_tool.run({
        "action": "call_tool",
        "tool_name": "read_file",
        "arguments": {"path": "README.md", "head": 5}
    })
    print(result)


if __name__ == "__main__":
    # 教程把两种方式写在一起，第二次赋值会覆盖第一次，这里拆成两个函数分别演示
    print("=== 方式1：自定义 Python 服务器 ===")
    custom_server_demo()

    print("\n=== 方式2：社区文件系统服务器 ===")
    filesystem_server_demo()
