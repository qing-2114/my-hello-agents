"""Reflection 智能体：生成代码，再通过反思迭代优化。

项目来源：https://hello-agents.datawhale.cc/
"""

from memory import Memory
from prompts import (
    INITIAL_PROMPT_TEMPLATE,
    REFLECT_PROMPT_TEMPLATE,
    REFINE_PROMPT_TEMPLATE,
)


class ReflectionAgent:
    """使用同一个 LLM 完成代码生成、评审和优化。"""

    def __init__(self, llm_client, max_iterations: int = 3) -> None:
        if not isinstance(max_iterations, int) or max_iterations < 0:
            raise ValueError("max_iterations 必须是非负整数")
        self.llm_client = llm_client
        self.memory = Memory()
        self.max_iterations = max_iterations

    def run(self, task: str) -> str:
        """返回最终代码文本；每次运行独立记忆，不自动执行生成代码。"""
        if not task.strip():
            raise ValueError("task 不能为空")
        self.memory = Memory()
        print(f"\n--- 开始处理任务 ---\n任务: {task}")

        print("\n--- 正在进行初始尝试 ---")
        initial_prompt = INITIAL_PROMPT_TEMPLATE.format(task=task)
        initial_code = self._get_llm_response(initial_prompt)
        self.memory.add_record("execution", initial_code)

        for i in range(self.max_iterations):
            print(f"\n--- 第 {i + 1}/{self.max_iterations} 轮迭代 ---")
            print("\n-> 正在进行反思...")
            last_code = self.memory.get_last_execution()
            reflect_prompt = REFLECT_PROMPT_TEMPLATE.format(task=task, code=last_code)
            feedback = self._get_llm_response(reflect_prompt)
            self.memory.add_record("reflection", feedback)

            # 避免把“并非无需改进”等反馈误判为结束信号。
            if feedback.strip().strip('。.!！“”\"\'') == "无需改进":
                print("\n✅ 反思认为代码已无需改进，任务完成。")
                break

            print("\n-> 正在进行优化...")
            refine_prompt = REFINE_PROMPT_TEMPLATE.format(
                task=task, last_code_attempt=last_code, feedback=feedback
            )
            refined_code = self._get_llm_response(refine_prompt)
            self.memory.add_record("execution", refined_code)
        else:
            if self.max_iterations:
                print("\n已达到最大迭代次数，返回最新代码。")

        final_code = self.memory.get_last_execution()
        assert final_code is not None
        print(f"\n--- 任务完成 ---\n最终生成的代码:\n{final_code}")
        return final_code

    def _get_llm_response(self, prompt: str) -> str:
        """调用客户端，获取完整流式响应；失败时停止，避免写入空记录。"""
        messages = [{"role": "user", "content": prompt}]
        response_text = self.llm_client.think(messages=messages)
        if not isinstance(response_text, str) or not response_text.strip():
            raise RuntimeError("LLM 未返回有效内容，本次任务已停止")
        return response_text


if __name__ == "__main__":
    import argparse
    import sys
    from pathlib import Path

    parser = argparse.ArgumentParser(description="生成 Python 代码并通过反思优化。")
    parser.add_argument(
        "task", nargs="?",
        default="编写一个Python函数，找出1到n之间所有的素数 (prime numbers)。",
    )
    parser.add_argument("--max-iterations", type=int, default=3)
    args = parser.parse_args()

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from llm_client import HelloAgentsLLM

    ReflectionAgent(HelloAgentsLLM(), args.max_iterations).run(args.task)
