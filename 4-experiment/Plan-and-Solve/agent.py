"""Plan-and-Solve 智能体：先规划，再逐步执行。

项目来源：<https://hello-agents.datawhale.cc/>。
"""

from typing import Optional

from executor import Executor
from planner import Planner


class PlanAndSolveAgent:
    def __init__(self, llm_client):
        """初始化智能体，同时创建规划器和执行器实例。"""
        self.llm_client = llm_client
        self.planner = Planner(self.llm_client)
        self.executor = Executor(self.llm_client)

    def run(self, question: str) -> Optional[str]:
        """先规划、后执行，返回最终答案；规划失败时返回 None。"""
        print(f"\n--- 开始处理问题 ---\n问题: {question}")

        plan = self.planner.plan(question)
        if not plan:
            print("\n--- 任务终止 --- \n无法生成有效的行动计划。")
            return None

        final_answer = self.executor.execute(question, plan)
        print(f"\n--- 任务完成 ---\n最终答案: {final_answer}")
        return final_answer


if __name__ == "__main__":
    import argparse
    import sys
    from pathlib import Path

    parser = argparse.ArgumentParser(description="通过规划和逐步执行回答问题。")
    parser.add_argument(
        "question",
        nargs="?",
        default=(
            "一个水果店周一卖出了15个苹果。周二卖出的苹果数量是周一的两倍。"
            "周三卖出的数量比周二少了5个。请问这三天总共卖出了多少个苹果？"
        ),
        help="要解决的问题（默认使用苹果销量题）",
    )
    args = parser.parse_args()

    # 复用第四章的客户端及其环境配置。
    experiment_dir = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(experiment_dir))
    from llm_client import HelloAgentsLLM

    agent = PlanAndSolveAgent(HelloAgentsLLM())
    agent.run(args.question)
