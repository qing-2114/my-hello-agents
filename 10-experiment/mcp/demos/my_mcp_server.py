"""第十章：最小的自定义 Python MCP 服务器，供 mcp_client_basics.py 连接。

项目来源：https://hello-agents.datawhale.cc/
通过 stdio 传输运行，由 MCPClient 以子进程方式启动，无需手动运行。
同时提供 MCP 的三类能力：工具（tools）、资源（resources）、提示（prompts）。
"""

from pathlib import Path

from fastmcp import FastMCP

mcp = FastMCP("my-server")

README_PATH = Path(__file__).resolve().parents[2] / "README.md"


@mcp.tool()
def add(a: float, b: float) -> float:
    """两数相加"""
    return a + b


@mcp.resource("file:///10-experiment/README.md", mime_type="text/markdown")
def experiment_readme() -> str:
    """第十章实验目录的 README"""
    return README_PATH.read_text(encoding="utf-8")


@mcp.prompt()
def code_review(language: str) -> str:
    """生成代码审查提示词"""
    return (
        f"请审查下面的 {language} 代码，指出潜在的 bug、可读性问题和性能问题，"
        f"并给出符合 {language} 惯用写法的修改建议。"
    )


if __name__ == "__main__":
    # 关闭 FastMCP 启动横幅，避免干扰客户端输出
    mcp.run(show_banner=False)
