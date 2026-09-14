# test_plan_solve_agent.py
"""第七章：MyPlanAndSolveAgent 的真实 API 测试（规划 + 逐步执行）。

项目来源：https://hello-agents.datawhale.cc/

运行（读取项目根目录 .env 中的 LLM_API_KEY、LLM_BASE_URL、LLM_MODEL_ID）：

    F:/my-hello-agent/.conda/python.exe ./7-experiment/tests/test_plan_solve_agent.py

说明：下面保留了示例中的 `from my_plan_solve_agent import MyPlanAndSolveAgent` 写法，
因此先把 7-experiment/agents 加入 sys.path；真实调用全部放在 ``main()`` 中，
由 ``if __name__ == "__main__":`` 触发。
"""

import sys
from pathlib import Path

AGENTS_DIR = Path(__file__).resolve().parents[1] / "agents"
if str(AGENTS_DIR) not in sys.path:
    sys.path.insert(0, str(AGENTS_DIR))

from dotenv import load_dotenv
from hello_agents.core.llm import HelloAgentsLLM
from my_plan_solve_agent import MyPlanAndSolveAgent


def main() -> None:
    """真实 API 冒烟测试：规划 + 逐步执行苹果销量题。"""
    # 加载环境变量
    load_dotenv()

    # 创建LLM实例
    llm = HelloAgentsLLM()

    # 创建自定义PlanAndSolveAgent
    agent = MyPlanAndSolveAgent(
        name="我的规划执行助手",
        llm=llm
    )

    # 测试复杂问题
    question = "一个水果店周一卖出了15个苹果。周二卖出的苹果数量是周一的两倍。周三卖出的数量比周二少了5个。请问这三天总共卖出了多少个苹果？"

    result = agent.run(question)
    print(f"\n最终结果: {result}")

    # 查看生成的计划与逐步执行轨迹
    print(f"执行计划: {agent.get_plan()}")
    print(f"执行轨迹:\n{agent.get_trajectory()}")

    # 查看对话历史
    print(f"对话历史: {len(agent.get_history())} 条消息")


if __name__ == "__main__":
    main()
