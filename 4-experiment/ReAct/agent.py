"""ReAct Agent 的核心循环实现。

项目来源：<https://hello-agents.datawhale.cc/>。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Optional


EXPERIMENT_DIR = Path(__file__).resolve().parent.parent
if str(EXPERIMENT_DIR) not in sys.path:
    sys.path.insert(0, str(EXPERIMENT_DIR))

from llm_client import HelloAgentsLLM
from prompts import REACT_PROMPT_TEMPLATE
from tools import ToolExecutor, tool_executor


class ReActAgent:
    """使用 Thought、Action 和 Observation 驱动工具调用的智能体。"""

    def __init__(
        self,
        llm_client: HelloAgentsLLM,
        tool_executor: ToolExecutor,
        max_steps: int = 5,
    ):
        if max_steps < 1:
            raise ValueError("max_steps 必须至少为 1。")

        self.llm_client = llm_client
        self.tool_executor = tool_executor
        self.max_steps = max_steps
        self.history: list[str] = []

    def run(self, question: str) -> Optional[str]:
        """运行 ReAct 智能体来回答一个问题。"""
        self.history = []

        for current_step in range(1, self.max_steps + 1):
            print(f"--- 第 {current_step} 步 ---")

            tools_desc = self.tool_executor.getAvailableTools()
            history_str = "\n".join(self.history)
            prompt = REACT_PROMPT_TEMPLATE.format(
                tools=tools_desc,
                question=question,
                history=history_str,
            )

            messages = [{"role": "user", "content": prompt}]
            response_text = self.llm_client.think(messages=messages)
            if not response_text:
                return "错误:LLM未能返回有效响应。"

            thought, action_text = self._parse_output(response_text)
            if thought:
                print(f"思考: {thought}")
            if not action_text:
                observation = "错误:未能解析到 Action 字段。请严格使用 Thought 和 Action 格式。"
                print(f"警告:{observation}，流程终止。")
                return None

            finish_match = re.fullmatch(r"Finish\[(.*)\]", action_text, flags=re.DOTALL)
            if finish_match:
                final_answer = finish_match.group(1)
                print(f"最终答案: {final_answer}")
                return final_answer

            tool_name, tool_input = self._parse_action(action_text)
            if not tool_name or not tool_input:
                observation = "错误:Action 必须是 工具名[工具输入] 或 Finish[最终答案]。"
            else:
                print(f"行动: {tool_name}[{tool_input}]")
                tool_function = self.tool_executor.getTool(tool_name)
                if not tool_function:
                    observation = f"错误:未找到名为 '{tool_name}' 的工具。"
                else:
                    try:
                        observation = str(tool_function(tool_input))
                    except Exception as exc:
                        observation = f"错误:工具 '{tool_name}' 执行失败: {exc}"

            print(f"观察: {observation}")
            self.history.append(f"Action: {action_text}")
            self.history.append(f"Observation: {observation}")

        print("已达到最大步数，流程终止。")
        return None

    def _parse_output(self, text: str) -> tuple[Optional[str], Optional[str]]:
        """解析 LLM 的输出，提取 Thought 和 Action。"""
        normalized_text = text.strip()
        if re.fullmatch(r"Finish\[.*\]", normalized_text, flags=re.DOTALL):
            return None, normalized_text

        thought_match = re.search(
            r"Thought:\s*(.*?)(?=\nAction:|\Z)", text, flags=re.DOTALL
        )
        action_match = re.search(
            r"^Action:\s*(.*?)\s*$", text, flags=re.DOTALL | re.MULTILINE
        )
        thought = thought_match.group(1).strip() if thought_match else None
        action = action_match.group(1).strip() if action_match else None
        return thought, action

    def _parse_action(self, action_text: str) -> tuple[Optional[str], Optional[str]]:
        """解析 Action 字符串，提取工具名称和输入。"""
        match = re.fullmatch(r"(\w+)\[(.*)\]", action_text.strip(), flags=re.DOTALL)
        if match:
            return match.group(1), match.group(2).strip()
        return None, None


if __name__ == "__main__":
    try:
        agent = ReActAgent(HelloAgentsLLM(), tool_executor)
    except ValueError as exc:
        print(f"配置错误:{exc}")
        raise SystemExit(1)

    print("ReAct Agent 已启动。输入 /exit、exit 或 quit 结束。")
    while True:
        try:
            question = input("\n你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n已结束 ReAct Agent。")
            break

        if question.lower() in {"/exit", "exit", "quit"}:
            print("已结束 ReAct Agent。")
            break
        if not question:
            continue

        answer = agent.run(question)
        if answer is None:
            print("本次未获得最终答案。")


__all__ = ["ReActAgent"]
