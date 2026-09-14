"""第七章实验：自定义高级搜索工具（多源整合）。

项目来源：https://hello-agents.datawhale.cc/

优先使用 Tavily，失败时回退到 SerpApi。密钥只从项目根目录 ``.env`` 读取，
不会打印或写入 API Key。
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from hello_agents import ToolRegistry

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"


def _load_search_environment() -> None:
    """加载项目根目录 .env，供 Tavily / SerpApi 读取密钥。"""
    if ENV_FILE.is_file():
        load_dotenv(ENV_FILE)


class MyAdvancedSearchTool:
    """自定义高级搜索工具类，展示多源整合和智能选择。"""

    def __init__(self) -> None:
        self.name = "my_advanced_search"
        self.description = "智能搜索工具，支持多个搜索源，自动选择最佳结果"
        self.search_sources: list[str] = []
        self.tavily_client = None
        self._setup_search_sources()

    def _setup_search_sources(self) -> None:
        """设置可用的搜索源。"""
        _load_search_environment()

        if os.getenv("TAVILY_API_KEY"):
            try:
                from tavily import TavilyClient

                self.tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
                self.search_sources.append("tavily")
                print("✅ Tavily搜索源已启用")
            except ImportError:
                print("⚠️ Tavily库未安装")

        if os.getenv("SERPAPI_API_KEY"):
            try:
                import serpapi  # noqa: F401

                self.search_sources.append("serpapi")
                print("✅ SerpApi搜索源已启用")
            except ImportError:
                print("⚠️ SerpApi库未安装")

        if self.search_sources:
            print(f"可用搜索源: {', '.join(self.search_sources)}")
        else:
            print("⚠️ 没有可用的搜索源，请配置API密钥")

    def search(self, query: str) -> str:
        """执行智能搜索。"""
        if not str(query).strip():
            return "❌ 错误:搜索查询不能为空"

        if not self.search_sources:
            return """❌ 没有可用的搜索源，请配置以下API密钥之一:

1. Tavily API: 设置环境变量 TAVILY_API_KEY
   获取地址: https://tavily.com/

2. SerpAPI: 设置环境变量 SERPAPI_API_KEY
   获取地址: https://serpapi.com/

配置后重新运行程序。"""

        print(f"开始智能搜索: {query}")

        for source in self.search_sources:
            try:
                if source == "tavily":
                    result = self._search_with_tavily(query)
                    if result and "未找到" not in result:
                        return f"Tavily AI搜索结果:\n\n{result}"

                elif source == "serpapi":
                    result = self._search_with_serpapi(query)
                    if result and "未找到" not in result:
                        return f"SerpApi Google搜索结果:\n\n{result}"

            except Exception as exc:
                print(f"⚠️ {source} 搜索失败: {exc}")
                continue

        return "❌ 所有搜索源都失败了，请检查网络连接和API密钥配置"

    def _search_with_tavily(self, query: str) -> str:
        """使用 Tavily 搜索。"""
        if self.tavily_client is None:
            raise RuntimeError("Tavily 客户端未初始化")

        response = self.tavily_client.search(query=query, max_results=3)

        if response.get("answer"):
            result = f"AI直接答案:{response['answer']}\n\n"
        else:
            result = ""

        result += "相关结果:\n"
        for i, item in enumerate(response.get("results", [])[:3], 1):
            result += f"[{i}] {item.get('title', '')}\n"
            result += f"    {item.get('content', '')[:150]}...\n\n"

        return result

    def _search_with_serpapi(self, query: str) -> str:
        """使用 SerpApi 搜索。

        教程示例使用 ``serpapi.GoogleSearch``（google-search-results 包）。
        当前环境安装的是官方 ``serpapi.Client``，两者都兼容。
        """
        import serpapi

        api_key = os.getenv("SERPAPI_API_KEY")
        if hasattr(serpapi, "GoogleSearch"):
            search = serpapi.GoogleSearch(
                {
                    "q": query,
                    "api_key": api_key,
                    "num": 3,
                }
            )
            results = search.get_dict()
        else:
            client = serpapi.Client(api_key=api_key)
            results = client.search(engine="google", q=query, num=3)

        result = "Google搜索结果:\n"
        organic = results.get("organic_results") if hasattr(results, "get") else None
        if organic:
            for i, res in enumerate(organic[:3], 1):
                result += f"[{i}] {res.get('title', '')}\n"
                result += f"    {res.get('snippet', '')}\n\n"

        return result


def create_advanced_search_registry() -> ToolRegistry:
    """创建包含高级搜索工具的注册表。"""
    registry = ToolRegistry()
    search_tool = MyAdvancedSearchTool()
    registry.register_function(
        name="advanced_search",
        description="高级搜索工具，整合Tavily和SerpAPI多个搜索源，提供更全面的搜索结果",
        func=search_tool.search,
    )
    return registry


if __name__ == "__main__":
    registry = create_advanced_search_registry()
    print("可用工具:", registry.list_tools())
    print(registry.execute_tool("advanced_search", ""))
    print(registry.execute_tool("advanced_search", "Datawhale Hello Agents"))
