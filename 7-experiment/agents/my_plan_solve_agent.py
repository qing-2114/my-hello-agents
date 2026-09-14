"""第七章实验：改进版 Plan-and-Solve Agent（先规划，再逐步执行）。

项目来源：https://hello-agents.datawhale.cc/

第四章的 PlanAndSolve Agent 只有两段：规划器把问题拆成 Python 列表形式的计划，
执行器再按计划逐步求解，并把已完成步骤的结果回灌给下一步。本实现保持这条主流程
不变，重点改进提示词与解析/容错：

1. 提示词（``MY_PLANNER_PROMPT`` / ``MY_EXECUTOR_PROMPT``，对应第四章的
   ``DEFAULT_PLANNER_PROMPT`` / ``DEFAULT_EXECUTOR_PROMPT``）：
   - 规划：步骤原子化、显式引用前序结果、限制在 2-5 步、不在计划里提前给出答案、
     最后一步必须回答原问题、只输出一个 Python 列表；
   - 执行：只输出当前步骤结论、复用历史结果不重算、先写算式再给结果、
     只使用题目与历史中出现过的数据、最后一步必须完整回答原问题。
2. 解析更健壮：兼容带 ```python / ```json 围栏、无围栏的裸列表，以及
   「1. 步骤」/「- 步骤」形式的列表；过滤空步骤和非字符串元素。
3. 出错自纠：计划解析失败时把格式要求回灌给模型重新规划；仍然失败时可以退回
   「把原问题当作单步计划直接作答」的兜底路径，而不是像第四章那样直接终止。
4. 过程可追溯：提供 ``get_plan()`` 与 ``get_trajectory()``，方便第七章的评估环节
   记录计划与实际执行结果。

用法::

    from hello_agents.core.llm import HelloAgentsLLM
    from my_plan_solve_agent import MyPlanAndSolveAgent

    agent = MyPlanAndSolveAgent(name="我的规划执行助手", llm=HelloAgentsLLM())
    print(agent.run("一个水果店周一卖出了15个苹果……"))
"""

from __future__ import annotations

import ast
import json
import re
from typing import Dict, List, Optional, Sequence

from hello_agents import Config, HelloAgentsLLM, Message
from hello_agents.core.agent import Agent


# 改进后的规划器提示词（对应第四章的 DEFAULT_PLANNER_PROMPT）。
MY_PLANNER_PROMPT = """你是一个顶级的AI规划专家。你的任务是将用户提出的复杂问题分解成一个由多个简单步骤组成的行动计划。

请严格遵守以下规则：
1. 每个步骤都是一个独立的、可执行的子任务，只做一件事，并写清楚这一步要用到的已知条件或前面步骤的结果。
2. 步骤必须严格按逻辑顺序排列；需要用到前一步结论时在步骤里写明，例如“用第1步算出的周二销量”。
3. 计划总步数控制在 2 到 5 步：简单问题不要过度拆分，复杂问题也不要把多个动作挤进同一步。
4. 步骤描述要具体，写明这一步要用到的数值和运算符（例如“用15×2算出周二销量”），不要使用“分析数据”“处理一下”这类含糊表述。
5. 计划只说明每一步要做什么，不要在步骤里提前算出结果或直接给出最终答案。
6. 最后一步必须明确要求回答用户的原始提问（例如“算出这三天总共卖出多少个苹果”），不能只停留在中间结果。

问题: {question}

请严格按照以下格式输出你的计划，```python 与 ``` 作为前后缀是必要的，代码块之外不要输出任何解释：
```python
["步骤1", "步骤2", "步骤3"]
```
"""

# 改进后的执行器提示词（对应第四章的 DEFAULT_EXECUTOR_PROMPT）。
MY_EXECUTOR_PROMPT = """你是一位顶级的AI执行专家。你的任务是严格按照给定的计划，一步步地解决问题。
你将收到原始问题、完整的计划、以及到目前为止已经完成的步骤和结果。
请你专注于解决“当前步骤”，并仅输出该步骤的最终答案，不要输出任何额外的解释或对话。

请严格遵守以下规则：
1. 只回答“当前步骤”，不要复述计划，不要输出“好的”“接下来”之类的开场白或结束语。
2. 历史步骤中已经得到的结果直接引用，不要重新计算，也不要改动已有结论。
3. 计算类步骤先写出算式再给出结果（例如 15 × 2 = 30），并按题目要求保留单位和精度。
4. 只使用原始问题和历史结果中出现过的数据，不要编造缺失的条件；确实缺少信息时，先说明假设再计算。
5. 如果当前步骤是计划中的最后一步，答案必须直接、完整地回答原始问题。

# 原始问题:
{question}

# 完整计划:
{plan}

# 历史步骤与结果:
{history}

# 当前步骤:
{current_step}

请仅输出针对“当前步骤”的回答:
"""

# 计划解析失败时回灌给模型的格式纠正要求。
PLAN_FORMAT_REMINDER = """你上一次的输出无法被解析成计划。请只输出一个 Python 字符串列表，形如：
```python
["步骤1", "步骤2", "步骤3"]
```
列表中的每个元素都是一句可执行的子任务描述；不要输出解释、标题、编号或列表以外的任何文字。"""

# 某一步骤没有返回内容时回灌给模型的提醒。
STEP_EMPTY_REMINDER = "你上一次没有返回任何内容。请只输出“当前步骤”的结论，不要输出其他说明。"

DEFAULT_PROMPTS: Dict[str, str] = {
    "planner": MY_PLANNER_PROMPT,
    "executor": MY_EXECUTOR_PROMPT,
}


# 兜底：匹配「1. 步骤」「- 步骤」这类列表行。
_LIST_ITEM_RE = re.compile(
    r"^[ \t]*(?:\d+[.、)）]|[-*+])[ \t]*(?P<body>.+?)[ \t]*$", re.MULTILINE
)


def _normalize_steps(raw: object) -> List[str]:
    """把解析结果规范化为非空的字符串步骤列表。"""
    if not isinstance(raw, (list, tuple)):
        return []
    steps: List[str] = []
    for item in raw:
        if not isinstance(item, str):
            continue
        step = item.strip().strip("\"'").strip()
        if step:
            steps.append(step)
    return steps


def _load_list_literal(literal: str) -> List[str]:
    """把一段方括号文本解析为步骤列表；两种解析器都失败时返回空列表。"""
    for loader in (ast.literal_eval, json.loads):
        try:
            steps = _normalize_steps(loader(literal))
        except (ValueError, SyntaxError, TypeError):
            continue
        if steps:
            return steps
    return []


def _iter_bracket_spans(text: str):
    """按出现顺序产出文本里每一个括号配平的 ``[...]`` 片段。

    扫描时会跳过字符串内部的方括号，因此步骤描述中带 ``[`` ``]`` 也能正确配平；
    片段之外的说明文字（围栏、标题、结尾总结）不会影响解析。
    """
    start = text.find("[")
    while start != -1:
        depth = 0
        quote = ""
        escaped = False
        for index in range(start, len(text)):
            char = text[index]
            if quote:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == quote:
                    quote = ""
                continue
            if char in "\"'":
                quote = char
            elif char == "[":
                depth += 1
            elif char == "]":
                depth -= 1
                if depth == 0:
                    yield text[start : index + 1]
                    break
        start = text.find("[", start + 1)


def extract_plan(text: str) -> List[str]:
    """从模型输出中提取步骤列表；解析失败返回空列表。

    依次尝试文本中的列表字面量（无论是否用 ``` 围栏包裹），最后兜底识别
    「1. 步骤」/「- 步骤」形式的列表行。
    """
    if not isinstance(text, str) or not text.strip():
        return []

    for span in _iter_bracket_spans(text):
        steps = _load_list_literal(span)
        if steps:
            return steps

    items = [
        match.group("body").strip().strip("\"'").strip()
        for match in _LIST_ITEM_RE.finditer(text)
    ]
    items = [item for item in items if item]
    return items if len(items) >= 2 else []


def _check_positive_int(label: str, value: object) -> int:
    """校验重试次数必须是正整数。"""
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{label} 必须是正整数")
    return value


def _build_messages(system_prompt: Optional[str], user_prompt: str) -> List[Dict[str, str]]:
    """按需前置 system 提示词，构造一次调用的 messages。"""
    messages: List[Dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_prompt})
    return messages


class MyPlanner:
    """规划器：把复杂问题分解为可执行的步骤列表。"""

    def __init__(
        self,
        llm: HelloAgentsLLM,
        prompt_template: Optional[str] = None,
        max_attempts: int = 2,
        system_prompt: Optional[str] = None,
    ) -> None:
        self.llm = llm
        self.prompt_template = prompt_template or MY_PLANNER_PROMPT
        self.max_attempts = _check_positive_int("max_attempts", max_attempts)
        self.system_prompt = system_prompt

    def plan(self, question: str, **kwargs) -> List[str]:
        """生成执行计划；解析失败时回灌格式要求重试，仍失败则返回空列表。"""
        print("--- 正在生成计划 ---")
        messages = _build_messages(
            self.system_prompt, self.prompt_template.format(question=question)
        )

        for attempt in range(1, self.max_attempts + 1):
            response_text = self.llm.invoke(messages, **kwargs)
            response_text = response_text if isinstance(response_text, str) else ""
            steps = extract_plan(response_text)

            if steps:
                formatted = "\n".join(
                    f"  {index}. {step}" for index, step in enumerate(steps, 1)
                )
                print(f"✅ 计划已生成（第 {attempt} 次尝试）:")
                print(formatted)
                return steps

            print(f"❌ 第 {attempt} 次输出无法解析为计划。原始响应:\n{response_text}")
            if attempt < self.max_attempts:
                print("⚠️ 回灌格式要求后重新规划。")
                messages.append({"role": "assistant", "content": response_text})
                messages.append({"role": "user", "content": PLAN_FORMAT_REMINDER})

        return []


class MyExecutor:
    """执行器：严格按计划逐步求解，并把结果回灌给后续步骤。"""

    def __init__(
        self,
        llm: HelloAgentsLLM,
        prompt_template: Optional[str] = None,
        max_attempts: int = 2,
        system_prompt: Optional[str] = None,
    ) -> None:
        self.llm = llm
        self.prompt_template = prompt_template or MY_EXECUTOR_PROMPT
        self.max_attempts = _check_positive_int("max_attempts", max_attempts)
        self.system_prompt = system_prompt
        self.records: List[Dict[str, str]] = []

    @staticmethod
    def format_plan(plan: Sequence[str]) -> str:
        """把计划渲染成带编号的文本，比直接传入 Python 列表更易读。"""
        return "\n".join(f"{index}. {step}" for index, step in enumerate(plan, 1))

    def execute(self, question: str, plan: Sequence[str], **kwargs) -> str:
        """按计划逐步执行，返回最后一步的答案（即最终答案）。

        Raises:
            RuntimeError: 某一步在重试后仍未返回任何内容时停止任务，
                避免把空结果当作有效结论传给后续步骤。
        """
        self.records = []
        history = ""
        final_answer = ""

        print("\n--- 正在执行计划 ---")
        for index, step in enumerate(plan, 1):
            print(f"\n-> 正在执行步骤 {index}/{len(plan)}: {step}")
            prompt = self.prompt_template.format(
                question=question,
                plan=self.format_plan(plan),
                history=history if history else "无",
                current_step=step,
            )
            answer = self._invoke_with_retry(prompt, index, **kwargs)

            # 当前步骤与结果会作为历史交给后续步骤。
            history += f"步骤 {index}: {step}\n结果: {answer}\n\n"
            self.records.append({"step": step, "result": answer})
            final_answer = answer
            print(f"✅ 步骤 {index} 已完成，结果: {answer}")

        return final_answer

    def _invoke_with_retry(self, prompt: str, index: int, **kwargs) -> str:
        """调用 LLM 并拒绝空响应；重试耗尽后抛出 RuntimeError。"""
        messages = _build_messages(self.system_prompt, prompt)
        for attempt in range(1, self.max_attempts + 1):
            response_text = self.llm.invoke(messages, **kwargs)
            response_text = response_text.strip() if isinstance(response_text, str) else ""
            if response_text:
                return response_text

            print(f"⚠️ 步骤 {index} 第 {attempt} 次调用没有返回内容。")
            if attempt < self.max_attempts:
                messages.append({"role": "user", "content": STEP_EMPTY_REMINDER})

        raise RuntimeError(f"LLM 在第 {index} 步没有返回有效内容，任务已停止")


class MyPlanAndSolveAgent(Agent):
    """改进版 Plan-and-Solve Agent：先规划、再逐步执行。

    相对于第四章 ``PlanAndSolveAgent`` 的差异：

    - 默认使用改进版提示词 ``MY_PLANNER_PROMPT`` / ``MY_EXECUTOR_PROMPT``，
      调用方仍可通过 ``custom_prompts`` 覆盖 ``planner`` / ``executor`` 中的任意一段；
    - 计划解析兼容围栏代码块、裸列表和编号列表，解析失败会把格式要求回灌给模型重试；
    - 规划彻底失败时默认退回「单步直接作答」，而不是直接终止任务；
    - 执行阶段拒绝空响应并重试，同时提供 ``get_plan()`` / ``get_trajectory()``
      便于记录和评估整个过程。
    """

    def __init__(
        self,
        name: str,
        llm: HelloAgentsLLM,
        system_prompt: Optional[str] = None,
        config: Optional[Config] = None,
        custom_prompts: Optional[Dict[str, str]] = None,
        max_plan_attempts: int = 2,
        max_step_attempts: int = 2,
        allow_direct_fallback: bool = True,
    ) -> None:
        """
        Args:
            name: Agent 名称。
            llm: LLM 实例，需实现 ``invoke(messages, **kwargs) -> str``。
            system_prompt: 可选的系统提示词，会前置到每次调用的 messages。
            config: 可选的配置对象。
            custom_prompts: 自定义提示词模板，可只覆盖 ``planner`` 或 ``executor``。
            max_plan_attempts: 规划最多尝试次数（含首次）。
            max_step_attempts: 单个步骤最多尝试次数（含首次）。
            allow_direct_fallback: 规划多次失败时是否退回单步直接作答。
        """
        super().__init__(name, llm, system_prompt, config)
        self.max_plan_attempts = _check_positive_int(
            "max_plan_attempts", max_plan_attempts
        )
        self.max_step_attempts = _check_positive_int(
            "max_step_attempts", max_step_attempts
        )
        self.allow_direct_fallback = bool(allow_direct_fallback)
        self.prompts = self._merge_prompts(custom_prompts)

        self.planner = MyPlanner(
            llm,
            self.prompts["planner"],
            self.max_plan_attempts,
            system_prompt,
        )
        self.executor = MyExecutor(
            llm,
            self.prompts["executor"],
            self.max_step_attempts,
            system_prompt,
        )
        self.last_plan: List[str] = []
        self.used_fallback = False

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
        for key, template in custom_prompts.items():
            if not isinstance(template, str) or not template.strip():
                raise ValueError(f"提示词模板 {key!r} 必须是非空字符串")
            prompts[key] = template
        return prompts

    def run(self, input_text: str, **kwargs) -> str:
        """先规划、后执行，返回最终答案。"""
        if not isinstance(input_text, str) or not input_text.strip():
            raise ValueError("input_text 不能为空")

        question = input_text.strip()
        self.used_fallback = False
        print(f"\n🤖 {self.name} 开始处理问题: {question}")

        plan = self.planner.plan(question, **kwargs)
        if not plan:
            if not self.allow_direct_fallback:
                final_answer = "无法生成有效的行动计划，任务终止。"
                print(f"\n--- 任务终止 ---\n{final_answer}")
                self._remember(question, final_answer)
                return final_answer

            plan = [f"直接回答原始问题：{question}"]
            self.used_fallback = True
            print("\n⚠️ 规划多次失败，退回「单步直接作答」兜底计划。")

        self.last_plan = list(plan)
        final_answer = self.executor.execute(question, plan, **kwargs)
        print(f"\n--- 任务完成 ---\n最终答案: {final_answer}")

        self._remember(question, final_answer)
        return final_answer

    def _remember(self, question: str, answer: str) -> None:
        """把一次任务的问答写入 Agent 历史记录。"""
        self.add_message(Message(question, "user"))
        self.add_message(Message(answer, "assistant"))

    def get_plan(self) -> List[str]:
        """返回最近一次 ``run()`` 实际执行的计划副本。"""
        return list(self.last_plan)

    def get_trajectory(self) -> str:
        """返回最近一次 ``run()`` 的逐步执行轨迹，便于记录与评估。"""
        sections = []
        for index, record in enumerate(self.executor.records, 1):
            sections.append(
                f"--- 步骤 {index}: {record['step']} ---\n{record['result']}"
            )
        return "\n\n".join(sections)
