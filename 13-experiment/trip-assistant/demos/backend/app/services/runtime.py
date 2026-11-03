"""从项目根目录读取配置，构建真实 LLM 和高德 MCP 工具。"""

from .amap_service import create_amap_mcp_tool
from .llm_service import create_llm


def create_runtime():
    llm = create_llm()
    tool = create_amap_mcp_tool()
    return llm, tool
