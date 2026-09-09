"""第七章实验：通用 Reflection Agent。

项目来源：https://hello-agents.datawhale.cc/

该实现借鉴第四章 Reflection Agent 的短期记忆和迭代结构，但不假设任务是
代码生成。它可以用于写作、总结、方案设计、翻译、问答和其他文本任务。
"""

from __future__ import annotations

import string
from typing import Dict, List, Optional

from hello_agents import Config, HelloAgentsLLM, Message
from hello_agents.core.agent import Agent


DEFAULT_PROMPTS: Dict[str, str] = {
    "initial": """
请根据以下要求完成任务:

任务: {task}

请提供一个完整、准确的回答。
""",
    "reflect": """
请仔细审查以下回答，并找出可能的问题或改进空间:

# 原始任务:
{task}

# 当前回答:
{content}

请分析这个回答的质量，指出不足之处，并提出具体的改进建议。
如果回答已经很好，请回答"无需改进"。
""",
    "refine": """
请根据反馈意见改进你的回答:

# 原始任务:
{task}

# 上一轮回答:
{last_attempt}

# 反馈意见:
{feedback}

请提供一个改进后的回答。
""",
}


class ReflectionMemory:
    """保存单次任务中的回答和反思记录，不写入磁盘。"""

    _VALID_TYPES = {"execution", "reflection"}

    def __init__(self) -> None:
        self.records: List[Dict[str, str]] = []

    def add_record(self, record_type: str, content: str) -> None:
        """按时间顺序添加一次回答或一次反思。"""
        if record_type not in self._VALID_TYPES:
            raise ValueError("record_type 必须是 'execution' 或 'reflection'")
        self.records.append({"type": record_type, "content": content})

    def get_last_execution(self) -> Optional[str]:
        """返回最近一次回答；尚未生成回答时返回 ``None``。"""
        for record in reversed(self.records):
            if record["type"] == "execution":
                return record["content"]
        return None

    def get_trajectory(self) -> str:
        """返回适合调试和评估的完整反思轨迹。"""
        sections = []
        for record in self.records:
            title = "当前回答" if record["type"] == "execution" else "反思反馈"
            sections.append(f"--- {title} ---\n{record['content']}")
        return "\n\n".join(sections)


class MyReflectionAgent(Agent):
    """通过“初始回答 -> 反思 -> 改进”循环完成通用文本任务。"""

    def __init__(
        self,
        name: str,
        llm: HelloAgentsLLM,
        system_prompt: Optional[str] = None,
        config: Optional[Config] = None,
        max_iterations: int = 3,
        custom_prompts: Optional[Dict[str, str]] = None,
    ) -> None:
        super().__init__(name, llm, system_prompt, config)
        if not isinstance(max_iterations, int) or max_iterations < 0:
            raise ValueError("max_iterations 必须是非负整数")

        self.max_iterations = max_iterations
        self.memory = ReflectionMemory()
        self.prompts = self._merge_prompts(custom_prompts)

    @staticmethod
    def _merge_prompts(custom_prompts: Optional[Dict[str, str]]) -> Dict[str, str]:
        """合并自定义提示词，允许只覆盖其中一段。"""
        prompts = DEFAULT_PROMPTS.copy()
        if custom_prompts is None:
            return prompts
        unknown = set(custom_prompts) - set(DEFAULT_PROMPTS)
        if unknown:
            names = ", ".join(sorted(unknown))
            raise ValueError(f"custom_prompts 包含未知模板: {names}")
        for name, template in custom_prompts.items():
            if not isinstance(template, str) or not template.strip():
                raise ValueError(f"提示词模板 {name!r} 必须是非空字符串")
            prompts[name] = template
        return prompts

    def run(self, input_text: str, **kwargs) -> str:
        """运行一次独立的 Reflection 流程并返回最终回答。"""
        if not isinstance(input_text, str) or not input_text.strip():
            raise ValueError("input_text 不能为空")

        # 每个任务使用独立短期记忆；Agent 的对话历史仍保留最终问答。
        self.memory = ReflectionMemory()
        task = input_text.strip()

        initial = self._get_llm_response(
            self.prompts["initial"].format(task=task), **kwargs
        )
        self.memory.add_record("execution", initial)

        for _ in range(self.max_iterations):
            last_attempt = self.memory.get_last_execution()
            if last_attempt is None:
                raise RuntimeError("反思前没有可供审查的回答")
            feedback = self._get_llm_response(
                self.prompts["reflect"].format(task=task, content=last_attempt),
                **kwargs,
            )
            self.memory.add_record("reflection", feedback)

            if self._is_no_improvement(feedback):
                break

            refined = self._get_llm_response(
                self.prompts["refine"].format(
                    task=task,
                    last_attempt=last_attempt,
                    feedback=feedback,
                ),
                **kwargs,
            )
            self.memory.add_record("execution", refined)

        final_result = self.memory.get_last_execution()
        if final_result is None:
            raise RuntimeError("任务没有生成有效回答")
        self.add_message(Message(task, "user"))
        self.add_message(Message(final_result, "assistant"))
        return final_result

    def _get_llm_response(self, prompt: str, **kwargs) -> str:
        """调用 LLM，并拒绝空响应，避免污染反思轨迹。"""
        messages = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        messages.append({"role": "user", "content": prompt})
        response = self.llm.invoke(messages, **kwargs)
        if not isinstance(response, str) or not response.strip():
            raise RuntimeError("LLM 未返回有效内容，本次任务已停止")
        return response.strip()

    @staticmethod
    def _is_no_improvement(feedback: str) -> bool:
        """只将完整的停止短语视为停止信号，避免误判普通反馈。"""
        candidate = feedback.strip().strip(string.punctuation + "，。！？、；：‘’“”《》")
        return candidate == "无需改进" or candidate.lower() == "no need for improvement"

    def get_trajectory(self) -> str:
        """获取本次任务的回答与反馈轨迹。"""
        return self.memory.get_trajectory()
