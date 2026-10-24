"""第十章：GitHub MCP 服务示例（同步 MCPTool）。

项目来源：https://hello-agents.datawhale.cc/
对应教程第十章「GitHub MCP 服务」示例代码，使用项目根目录 .conda 环境。

需要在项目根目录 .env 中配置 GITHUB_PERSONAL_ACCESS_TOKEN（教程写的是手动设置 shell 环境变量，
本项目统一从 .env 读取）。MCPTool 会按 server-github 自动检测并把该变量传给服务器子进程。
注意：@modelcontextprotocol/server-github 已在 npm 上标记为弃用，但仍可安装运行。
"""

import os
import sys
from pathlib import Path

# Windows 控制台默认 GBK，hello-agents/fastmcp 打印的 emoji 会导致 MCP 调用失败
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
from hello_agents.tools import MCPTool

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(ENV_FILE)

if not os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN"):
    sys.exit(f"未配置 GITHUB_PERSONAL_ACCESS_TOKEN，请在 {ENV_FILE} 中添加后再运行")

# 创建 GitHub MCP 工具
github_tool = MCPTool(
    name="github",
    server_command=["npx", "-y", "@modelcontextprotocol/server-github"]
)

# 1. 列出可用工具
print("📋 可用工具：")
result = github_tool.run({"action": "list_tools"})
print(result)

# 2. 搜索仓库
print("\n🔍 搜索仓库：")
result = github_tool.run({
    "action": "call_tool",
    "tool_name": "search_repositories",
    "arguments": {
        "query": "AI agents language:python",
        "page": 1,
        "perPage": 3
    }
})
print(result)
