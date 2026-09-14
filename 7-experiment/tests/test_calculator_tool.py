"""第七章：自定义计算器工具的离线单元测试与真实 API 冒烟测试。

项目来源：https://hello-agents.datawhale.cc/

离线测试（不访问外部服务）：

    F:/my-hello-agent/.conda/python.exe -m unittest discover -s ./7-experiment/tests -p "test_calculator_tool.py" -v

真实 API 冒烟（读取项目根目录 .env 中的 LLM_API_KEY、LLM_BASE_URL、LLM_MODEL_ID）：

    F:/my-hello-agent/.conda/python.exe ./7-experiment/tests/test_calculator_tool.py

``unittest discover`` 导入本文件时不会发起 API 请求；真实调用全部放在 ``main()`` 中。
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

from dotenv import load_dotenv


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = EXPERIMENT_ROOT.parent
ENV_FILE = PROJECT_ROOT / ".env"
REQUIRED_ENV_VARS = ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL_ID")

if str(EXPERIMENT_ROOT) not in sys.path:
    sys.path.insert(0, str(EXPERIMENT_ROOT))

from tools.my_calculator_tool import (  # noqa: E402
    create_calculator_registry,
    my_calculate,
)


class MyCalculatorToolTests(unittest.TestCase):
    def test_basic_arithmetic_respects_precedence(self) -> None:
        self.assertEqual(my_calculate("2 + 3 * 4"), "14")
        self.assertEqual(my_calculate("(15 + 9) * 3"), "72")

    def test_sqrt_and_pi(self) -> None:
        self.assertEqual(my_calculate("sqrt(16)"), "4.0")
        self.assertTrue(my_calculate("pi").startswith("3.14"))

    def test_unary_minus(self) -> None:
        self.assertEqual(my_calculate("-5 + 3"), "-2")

    def test_empty_expression(self) -> None:
        self.assertEqual(my_calculate(""), "计算表达式不能为空")
        self.assertEqual(my_calculate("   "), "计算表达式不能为空")

    def test_unsupported_or_invalid_expression(self) -> None:
        self.assertEqual(my_calculate("2 ** 3"), "计算失败，请检查表达式格式")
        self.assertEqual(my_calculate("import os"), "计算失败，请检查表达式格式")
        self.assertEqual(my_calculate("sqrt()"), "计算失败，请检查表达式格式")

    def test_registry_registers_and_executes(self) -> None:
        registry = create_calculator_registry()
        self.assertIn("my_calculator", registry.list_tools())
        self.assertIn("my_calculator", registry.get_tools_description())
        self.assertEqual(registry.execute_tool("my_calculator", "8 / 2"), "4.0")


def _load_project_environment() -> None:
    if not ENV_FILE.is_file():
        raise FileNotFoundError(f"未找到项目环境配置文件：{ENV_FILE}")

    load_dotenv(ENV_FILE)
    missing = [name for name in REQUIRED_ENV_VARS if not os.getenv(name)]
    if missing:
        raise RuntimeError(
            f"请在 {ENV_FILE} 中配置以下变量：{', '.join(missing)}"
        )


def main() -> None:
    """真实 API 冒烟测试：MySimpleAgent 调用自定义 my_calculator 工具。"""
    from hello_agents import HelloAgentsLLM

    from agents.my_simple_agent import MySimpleAgent

    _load_project_environment()
    llm = HelloAgentsLLM()
    registry = create_calculator_registry()
    agent = MySimpleAgent(
        name="计算器助手",
        llm=llm,
        system_prompt="你是一个会使用工具的助手。需要计算时必须调用 my_calculator，不要自己心算。",
        tool_registry=registry,
    )

    question = (
        "请调用 my_calculator 计算 (15 + 9) * 3 的结果，"
        "再用中文给出最终答案。不要自己心算。"
    )
    result = agent.run(question)
    print(f"\n最终结果: {result}")
    print(f"可用工具: {agent.list_tools()}")
    print(f"对话历史: {len(agent.get_history())} 条消息")


if __name__ == "__main__":
    main()
