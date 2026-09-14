# test_my_calculator.py
"""第七章：自定义计算器工具的教程式测试。

项目来源：https://hello-agents.datawhale.cc/

保留示例中的 `from my_calculator_tool import create_calculator_registry` 写法，
因此先把 7-experiment/tools 加入 sys.path。

本地工具测试不访问外部服务；与 LLM 的集成测试读取项目根目录 .env
中的 LLM_API_KEY、LLM_BASE_URL、LLM_MODEL_ID。真实调用由
``if __name__ == "__main__":`` 触发，``unittest discover`` 导入本文件时
不会发起 API 请求。

运行：

    F:/my-hello-agent/.conda/python.exe ./7-experiment/tests/test_my_calculator.py
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"
REQUIRED_ENV_VARS = ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL_ID")

if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from my_calculator_tool import create_calculator_registry  # noqa: E402


def _load_project_environment() -> None:
    """加载项目根目录 .env，并确认 LLM 配置完整。"""
    if not ENV_FILE.is_file():
        raise FileNotFoundError(f"未找到项目环境配置文件：{ENV_FILE}")

    load_dotenv(ENV_FILE)
    missing = [name for name in REQUIRED_ENV_VARS if not os.getenv(name)]
    if missing:
        raise RuntimeError(
            f"请在 {ENV_FILE} 中配置以下变量：{', '.join(missing)}"
        )


def test_calculator_tool():
    """测试自定义计算器工具"""

    # 创建包含计算器的注册表
    registry = create_calculator_registry()

    print(" 测试自定义计算器工具\n")

    # 简单测试用例
    test_cases = [
        "2 + 3",           # 基本加法
        "10 - 4",          # 基本减法
        "5 * 6",           # 基本乘法
        "15 / 3",          # 基本除法
        "sqrt(16)",        # 平方根
    ]

    for i, expression in enumerate(test_cases, 1):
        print(f"测试 {i}: {expression}")
        result = registry.execute_tool("my_calculator", expression)
        print(f"结果: {result}\n")


def test_with_simple_agent():
    """测试与SimpleAgent的集成"""
    from hello_agents import HelloAgentsLLM

    _load_project_environment()

    # 创建LLM客户端
    llm = HelloAgentsLLM()

    # 创建包含计算器的注册表
    registry = create_calculator_registry()

    print(" 与SimpleAgent集成测试:")

    # 模拟SimpleAgent使用工具的场景
    user_question = "请帮我计算 sqrt(16) + 2 * 3"

    print(f"用户问题: {user_question}")

    # 使用工具计算
    calc_result = registry.execute_tool("my_calculator", "sqrt(16) + 2 * 3")
    print(f"计算结果: {calc_result}")

    # 构建最终回答
    final_messages = [
        {"role": "user", "content": f"计算结果是 {calc_result}，请用自然语言回答用户的问题:{user_question}"}
    ]

    print("\n SimpleAgent的回答:")
    # hello-agents 的 think() 已在内部流式打印，这里只把生成器消费完
    for _ in llm.think(final_messages):
        pass
    print()


if __name__ == "__main__":
    test_calculator_tool()
    test_with_simple_agent()
