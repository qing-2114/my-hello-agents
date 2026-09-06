"""Plan-and-Solve 的规划器。"""

import ast

from prompts import PLANNER_PROMPT_TEMPLATE


class Planner:
    def __init__(self, llm_client):
        self.llm_client = llm_client

    def plan(self, question: str) -> list[str]:
        """根据用户问题生成行动计划；响应解析失败时返回空列表。"""
        prompt = PLANNER_PROMPT_TEMPLATE.format(question=question)
        messages = [{"role": "user", "content": prompt}]

        print("--- 正在生成计划 ---")
        # think() 内部处理流式输出，并返回完整的响应文本。
        response_text = self.llm_client.think(messages=messages) or ""
        print(f"✅ 计划已生成:\n{response_text}")

        try:
            plan_str = response_text.split("```python")[1].split("```")[0].strip()
            # literal_eval 解析 Python 字面量，不执行任意 Python 代码。
            plan = ast.literal_eval(plan_str)
            if not isinstance(plan, list) or not all(
                isinstance(step, str) for step in plan
            ):
                raise ValueError("计划必须是由字符串组成的 Python 列表")
            return plan
        except (ValueError, SyntaxError, IndexError) as e:
            print(f"❌ 解析计划时出错: {e}")
            print(f"原始响应: {response_text}")
            return []
        except Exception as e:
            print(f"❌ 解析计划时发生未知错误: {e}")
            return []
