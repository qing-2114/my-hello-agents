"""第十章：使用异步 MCPClient 连接 MCP 服务器、发现可用工具、安全调用工具，以及使用资源和提示。

项目来源：https://hello-agents.datawhale.cc/
对应教程第十章「连接 MCP 服务器」「发现可用工具」「错误处理」「资源与提示」示例代码，使用项目根目录 .conda 环境。
依赖 Node.js（npx），首次运行会从 npm 下载 @modelcontextprotocol/server-filesystem。
"""

import asyncio
import sys
from pathlib import Path

# Windows 控制台默认 GBK，hello-agents/fastmcp 打印的 emoji 会导致 MCP 调用失败
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from hello_agents.protocols import MCPClient

DEMOS_DIR = Path(__file__).resolve().parent
# 文件系统服务器只允许访问该目录；教程写的是 "."，这里固定为本实验目录，避免受运行时工作目录影响
FS_ROOT = str(DEMOS_DIR.parents[1])
# 自定义服务器脚本路径；教程的 my_mcp_server.py 未提供，本目录补充了一个最小实现
CUSTOM_SERVER = str(DEMOS_DIR / "my_mcp_server.py")


def filesystem_client() -> MCPClient:
    # npx 会自动下载并运行 @modelcontextprotocol/server-filesystem 包
    return MCPClient(["npx", "-y", "@modelcontextprotocol/server-filesystem", FS_ROOT])


async def connect_to_server():
    # 方式1：连接到社区提供的文件系统服务器
    client = filesystem_client()

    # 使用 async with 确保连接正确关闭
    async with client:
        tools = await client.list_tools()
        print(f"可用工具: {[t['name'] for t in tools]}")

    # 方式2：连接到自定义的 Python MCP 服务器
    client = MCPClient(["python", CUSTOM_SERVER])
    async with client:
        tools = await client.list_tools()
        print(f"可用工具: {[t['name'] for t in tools]}")
        result = await client.call_tool("add", {"a": 10, "b": 20})
        print(f"add(10, 20) = {result}")


async def discover_tools():
    client = filesystem_client()

    async with client:
        # 获取所有可用工具
        tools = await client.list_tools()

        print(f"服务器提供了 {len(tools)} 个工具：")
        for tool in tools:
            print(f"\n工具名称: {tool['name']}")
            print(f"描述: {tool.get('description') or '无描述'}")

            # 打印参数信息
            # 注意：hello-agents 0.2.8 的 list_tools() 返回键名为 input_schema，教程写的 inputSchema 取不到
            schema = tool.get("input_schema") or {}
            if "properties" in schema:
                print("参数:")
                for param_name, param_info in schema["properties"].items():
                    param_type = param_info.get("type", "any")
                    param_desc = param_info.get("description", "")
                    print(f"  - {param_name} ({param_type}): {param_desc}")


async def safe_tool_call():
    client = filesystem_client()

    async with client:
        try:
            # 尝试读取可能不存在的文件
            result = await client.call_tool("read_file", {"path": "nonexistent.txt"})
            print(result)
        except Exception as e:
            print(f"工具调用失败: {e}")
            # 可以选择重试、使用默认值或向用户报告错误


# hello-agents 0.2.8 的 list_resources / list_prompts / read_resource 仍按旧版 fastmcp 的返回格式解析
# （取 .resources / .prompts / .contents），而当前 fastmcp 直接返回列表：前两个抛 AttributeError，
# read_resource 静默返回 None。以下兼容函数改用底层 fastmcp 客户端 client.client，返回格式与 hello-agents 一致。
async def list_resources_compat(client: MCPClient) -> list[dict]:
    resources = await client.client.list_resources()
    return [
        {"uri": str(r.uri), "name": r.name or "", "description": r.description or "", "mime_type": r.mimeType}
        for r in resources
    ]


async def read_resource_compat(client: MCPClient, uri: str) -> str:
    contents = await client.client.read_resource(uri)
    return "\n".join(getattr(c, "text", "") for c in contents)


async def list_prompts_compat(client: MCPClient) -> list[dict]:
    prompts = await client.client.list_prompts()
    return [
        {"name": p.name, "description": p.description or "", "arguments": p.arguments or []}
        for p in prompts
    ]


async def use_resources_and_prompts():
    # 文件系统服务器只提供工具，调用 resources/prompts 会报 Method not found，这里连接自定义服务器
    # 注意：这几个方法都是 async，教程代码漏写了 await
    client = MCPClient(["python", CUSTOM_SERVER])

    async with client:
        # 列出可用资源
        resources = await list_resources_compat(client)
        print(f"可用资源：{[r['uri'] for r in resources]}")

        # 读取资源（只打印前 3 行）
        resource_content = await read_resource_compat(client, "file:///10-experiment/README.md")
        preview = "\n".join(resource_content.splitlines()[:3])
        print(f"资源内容（前 3 行）：\n{preview}")

        # 列出可用提示
        prompts = await list_prompts_compat(client)
        print(f"\n可用提示：{[p['name'] for p in prompts]}")

        # 获取提示内容
        prompt = await client.get_prompt("code_review", {"language": "python"})
        print(f"提示内容：{prompt}")


async def main():
    print("=== 连接 MCP 服务器 ===")
    await connect_to_server()

    print("\n=== 发现可用工具 ===")
    await discover_tools()

    print("\n=== 安全调用工具（错误处理） ===")
    await safe_tool_call()

    print("\n=== 资源与提示 ===")
    await use_resources_and_prompts()


if __name__ == "__main__":
    asyncio.run(main())
