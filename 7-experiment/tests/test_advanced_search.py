# test_advanced_search.py
"""第七章：自定义高级搜索工具的教程式测试。

项目来源：https://hello-agents.datawhale.cc/

保留示例中的 `from my_advanced_search import ...` 写法，因此先把
7-experiment/tools 加入 sys.path。真实 Tavily/SerpApi 调用由
``if __name__ == "__main__":`` 触发；``unittest discover`` 导入本文件时
不会发起搜索请求。

运行（读取项目根目录 .env 中的 TAVILY_API_KEY / SERPAPI_API_KEY）：

    F:/my-hello-agent/.conda/python.exe ./7-experiment/tests/test_advanced_search.py
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"

if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from my_advanced_search import (  # noqa: E402
    MyAdvancedSearchTool,
    create_advanced_search_registry,
)


def _load_search_environment() -> None:
    """加载项目根目录 .env。"""
    if not ENV_FILE.is_file():
        raise FileNotFoundError(f"未找到项目环境配置文件：{ENV_FILE}")

    load_dotenv(ENV_FILE)


def test_advanced_search():
    """测试高级搜索工具"""
    _load_search_environment()

    # 创建包含高级搜索工具的注册表
    registry = create_advanced_search_registry()

    print(" 测试高级搜索工具\n")

    # 测试查询
    test_queries = [
        "Python编程语言的历史",
        "人工智能的最新发展",
        "2024年科技趋势"
    ]

    for i, query in enumerate(test_queries, 1):
        print(f"测试 {i}: {query}")
        result = registry.execute_tool("advanced_search", query)
        print(f"结果: {result}\n")
        print("-" * 60 + "\n")


def test_api_configuration():
    """测试API配置检查"""
    _load_search_environment()
    print(" 测试API配置检查:")

    # 直接创建搜索工具实例
    search_tool = MyAdvancedSearchTool()

    # 如果没有配置API，会显示配置提示
    result = search_tool.search("机器学习算法")
    print(f"搜索结果: {result}")


def test_with_agent():
    """测试与Agent的集成"""
    print("\n 与Agent集成测试:")
    print("高级搜索工具已准备就绪，可以与Agent集成使用")

    # 显示工具描述
    registry = create_advanced_search_registry()
    tools_desc = registry.get_tools_description()
    print(f"工具描述:\n{tools_desc}")


if __name__ == "__main__":
    test_advanced_search()
    test_api_configuration()
    test_with_agent()
