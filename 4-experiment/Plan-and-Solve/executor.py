"""Plan-and-Solve 的执行器。"""

from prompts import EXECUTOR_PROMPT_TEMPLATE


class Executor:
    def __init__(self, llm_client):
        self.llm_client = llm_client

    def execute(self, question: str, plan: list[str]) -> str:
        """逐步执行计划，返回最后一步的答案；空计划返回空字符串。"""
        history = ""
        response_text = ""

        print("\n--- 正在执行计划 ---")

        for i, step in enumerate(plan):
            print(f"\n-> 正在执行步骤 {i+1}/{len(plan)}: {step}")

            prompt = EXECUTOR_PROMPT_TEMPLATE.format(
                question=question,
                plan=plan,
                history=history if history else "无",
                current_step=step,
            )
            messages = [{"role": "user", "content": prompt}]
            response_text = self.llm_client.think(messages=messages) or ""

            # 将当前步骤和结果传给后续步骤。
            history += f"步骤 {i+1}: {step}\n结果: {response_text}\n\n"
            print(f"✅ 步骤 {i+1} 已完成，结果: {response_text}")

        return response_text
