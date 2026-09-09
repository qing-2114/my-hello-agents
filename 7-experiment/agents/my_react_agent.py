"""第七章实验：改进版 ReAct Agent（推理 + 行动）。

在「保持 ReAct 核心逻辑不变」的前提下，改进 hello-agents 自带的
``ReActAgent``。核心循环仍然是：构建提示词 -> 调用 LLM -> 解析
Thought/Action -> 命中 Finish 则结束 -> 否则执行工具并把 Observation 回灌，
直到得出答案或达到最大步数。

主要改进点：
1. 提示词（``MY_REACT_PROMPT``）：Thought/Action 不再加粗、明确禁止代码围栏与
   多余开场白/结语，显著降低模型输出「解析不到 Action」的格式错误；
2. 解析更健壮：容忍代码围栏、加粗标记、多行思考、多个步骤、行尾附注，
   并正确提取 ``工具名[入参]`` / ``Finish[最终答案]``；
3. 出错自纠：当模型没有给出可用 Action（或格式无效）时，把格式要求作为一条
   Observation 回灌给模型，让它用剩余步数自我纠正，而不是像父类那样直接终止；
4. 防幻觉（经 A/B 实验验证）：Finish 的答案必须以本轮 Observation 为据；若某信息
   （如官网地址）未被搜索结果确认，须如实说明「未找到」，不得编造新网址。

用法与框架自带的 ``ReActAgent`` 完全一致：:

    agent = MyReActAgent(name="助手", llm=llm, tool_registry=registry, max_steps=5)
    answer = agent.run("请帮我计算 2+3*4")

运行离线单元测试：

    F:\\my-hello-agent\\.conda\\python.exe -m unittest discover -s .\\7-experiment\\tests -p "test_*.py" -v
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

from hello_agents import Config, HelloAgentsLLM, Message, ReActAgent, ToolRegistry

# 改进后的 ReAct 提示词模板。
# 相对框架默认版本：Thought/Action 不再加粗回显；明确禁止代码围栏、开场白和结语；
# 提示 Observation 报错时应换参数/换工具重试；第 7、8 条防幻觉约束经 A/B 实验
# 验证（追加后同问题连跑不再输出未观察到的新网址，并如实说明"未找到"）。
MY_REACT_PROMPT = """你是一个具备推理和行动能力的AI助手。你可以通过思考分析问题，然后调用合适的工具来获取信息，最终给出准确的答案。

## 可用工具
{tools}

## 工作流程
请严格按照以下格式进行回应，每次只能执行一个步骤：

Thought: 分析当前问题，思考需要什么信息或采取什么行动。
Action: 选择一个行动，格式必须是以下之一：
- `{{tool_name}}[{{tool_input}}]` - 调用指定工具，{{tool_input}} 是该工具的入参字符串
- `Finish[最终答案]` - 当你有足够信息给出最终答案时

## 重要提醒
1. 每次回应必须包含 Thought 和 Action 两部分，且两行都要从行首开始。
2. 工具调用的格式必须严格遵循：工具名[参数]，例如 `python_calculator[2+3*4]`。
3. 只有当你确信有足够信息回答问题时，才使用 Finish，并把完整答案写在方括号内。
4. 如果工具返回的信息不够，继续使用其他工具或相同工具的不同参数。
5. 如果 Observation 是错误信息，先分析原因，再换参数或换工具重试；不要用相同参数反复调用同一工具。
6. 你的整段回复只应包含上面的 Thought 和 Action，不要有开场白、解释、结语，也不要使用代码围栏或加粗。
7. Finish 的最终答案必须只基于上方「执行历史」的 Observation 中已经出现的信息，不要编造其中没有出现的网址、数字、日期或任何具体事实。
8. 若某个信息（例如官网地址）在搜索结果中没有出现，请在 Finish 中如实说明“未找到官方地址”，并只给出已被 Observation 确认的链接（如 GitHub 仓库）；绝对不要猜测一个看似合理但未被证实的新网址。

## 当前任务
**Question:** {question}

## 执行历史
{history}

现在开始你的推理和行动："""


# 识别 Thought / Action 标记行。容忍行首/冒号两侧的空白、**、*、#、>、`、-，
# 以及 `**Thought:** 内容` 这种加粗标记（含闭合侧的 `**`），还支持中英文冒号。
_LABEL_LINE = re.compile(
    r"^\s*(?:\*\*|\*|#|>|`|-|_)*\s*"
    r"(?P<label>Thought|Action|思考|行动)\s*[:：]\s*"
    r"(?:\*\*|\*|#|>|`|-|_)*\s*(?P<body>.*?)\s*$",
    re.IGNORECASE,
)

# 识别「工具名[入参]」动作令牌，贪婪匹配到最后一个 ]，
# 从而容忍入参内部出现方括号，以及动作之后跟有多余文字。
_ACTION_TOKEN = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\[(.*)\]", re.DOTALL)


def _strip_code_fence(text: str) -> str:
    """去掉模型偶尔会用 ``` 或 ~~~ 包裹整段回复的围栏行。"""
    return re.sub(r"^\s*(?:```+|~~~+).*$", "", text, flags=re.MULTILINE)


def _canon_label(label: str) -> str:
    """把中英文标记统一成内部使用的标签。"""
    return "thought" if label.lower() in {"thought", "思考"} else "action"


class MyReActAgent(ReActAgent):
    """改进版 ReAct Agent：推理与行动结合的智能体。

    与父类 ``ReActAgent`` 的差异：
    - 默认使用改进版提示词 ``MY_REACT_PROMPT``（仍可用 ``custom_prompt`` 覆盖）；
    - ``run`` 对解析失败采取「回灌格式提示、继续尝试」的自纠策略，
      而不是遇到一次格式错误就终止流程；
    - 提供更健壮的 ``_parse_output`` / ``_parse_action`` 解析实现。
    """

    def __init__(
        self,
        name: str,
        llm: HelloAgentsLLM,
        tool_registry: ToolRegistry,
        system_prompt: Optional[str] = None,
        config: Optional[Config] = None,
        max_steps: int = 5,
        custom_prompt: Optional[str] = None,
    ) -> None:
        # 改进版提示词优先；调用方仍可通过 custom_prompt 完全自定义模板。
        super().__init__(
            name=name,
            llm=llm,
            tool_registry=tool_registry,
            system_prompt=system_prompt,
            config=config,
            max_steps=max_steps,
            custom_prompt=custom_prompt or MY_REACT_PROMPT,
        )
        print(f"✅ {name} 初始化完成，最大步数: {max_steps}")

    def run(self, input_text: str, **kwargs) -> str:
        """运行 ReAct Agent 主循环。

        核心循环与父类一致，仅调整出错时的处理方式：

        1. 构建提示词（工具描述 + 问题 + 执行历史）；
        2. 调用 LLM 得到 Thought / Action；
        3. 命中 ``Finish[...]`` 则返回最终答案；
        4. 否则解析出 ``工具名[入参]`` 并执行工具，把 Observation 追加到历史；
        5. 未超过 ``max_steps`` 时回到第 1 步。

        区别在于：当模型没给出 Action、或 Action 格式无效时，不再像父类那样
        直接 ``break`` 终止，而是把具体的格式要求作为 Observation 回灌，
        让模型利用剩余步数自我纠正。
        """
        self.current_history = []
        current_step = 0

        print(f"\n🤖 {self.name} 开始处理问题: {input_text}")

        while current_step < self.max_steps:
            current_step += 1
            print(f"\n--- 第 {current_step} 步 ---")

            # 1. 构建提示词
            tools_desc = self.tool_registry.get_tools_description()
            history_str = "\n".join(self.current_history)
            prompt = self.prompt_template.format(
                tools=tools_desc,
                question=input_text,
                history=history_str,
            )

            # 2. 调用 LLM
            messages = [{"role": "user", "content": prompt}]
            response_text = self.llm.invoke(messages, **kwargs)

            if not response_text or not response_text.strip():
                print("❌ 错误：LLM 未返回有效响应，终止流程。")
                break

            # 3. 解析输出
            thought, action = self._parse_output(response_text)

            if thought:
                print(f"🤔 思考: {thought}")

            # 4. 统一先解析动作令牌，再判断是 Finish 还是工具调用
            tool_name, tool_input = self._parse_action(action)

            if tool_name is not None and tool_name.lower() == "finish":
                final_answer = tool_input if tool_input is not None else ""
                if not final_answer:
                    print("⚠️ Finish 未携带最终答案，回灌提示后继续。")
                    self.current_history.append(
                        "Observation: 你输出了 Finish 但方括号内没有内容，"
                        "请在 Finish[最终答案] 中补上给用户的完整答案后重新输出。"
                    )
                    continue

                print(f"🎉 最终答案: {final_answer}")

                # 保存到历史记录
                self.add_message(Message(input_text, "user"))
                self.add_message(Message(final_answer, "assistant"))
                return final_answer

            if not tool_name or tool_input is None or tool_input == "":
                # Action 缺失或格式无效：把具体要求回灌，让模型自我纠正
                print("⚠️ Action 无法解析，回灌格式提示后继续。")
                self.current_history.append(
                    f"Observation: 你的 Action「{action or '（空）'}」格式无效，"
                    "必须是 工具名[入参] 或 Finish[最终答案]，请重新输出一行 Thought 和一行 Action。"
                )
                continue

            # 5. 执行工具调用
            print(f"🎬 行动: {tool_name}[{tool_input}]")
            observation = self.tool_registry.execute_tool(tool_name, tool_input)
            print(f"👀 观察: {observation}")

            # 更新执行历史（只记录规范化的动作令牌，避免把行尾附注一并带回）
            self.current_history.append(f"Action: {tool_name}[{tool_input}]")
            self.current_history.append(f"Observation: {observation}")

        # 达到最大步数
        print("⏰ 已达到最大步数，流程终止。")
        final_answer = "抱歉，我无法在限定步数内完成这个任务。"

        # 保存到历史记录
        self.add_message(Message(input_text, "user"))
        self.add_message(Message(final_answer, "assistant"))
        return final_answer

    def _parse_output(self, text: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
        """解析 LLM 输出，提取最后一段 Thought 和最后一段 Action。

        返回 ``(thought, action)``。两者均可为空字符串以外的 ``None``。
        支持：
        - 代码围栏包裹（````` ``` `` 或 `~~~`）；
        - 行首的加粗/列表/引用等杂散标记；
        - Thought 正文跨行（后续行会被并入同一块）；
        - 模型一次性输出多组 Thought/Action 时，取最后一组。
        """
        if not text:
            return None, None

        # 按行切分，先去掉代码围栏行
        raw_lines = [
            line.strip() for line in _strip_code_fence(text).splitlines()
        ]

        # 把连续的行按标记切块：标记行开启新块，普通行并入当前块
        blocks: List[Tuple[str, List[str]]] = []
        current_key: Optional[str] = None
        current_lines: List[str] = []

        for line in raw_lines:
            match = _LABEL_LINE.match(line)
            if match:
                if current_key is not None:
                    blocks.append((current_key, current_lines))
                current_key = _canon_label(match.group("label"))
                current_lines = [match.group("body").strip()]
            elif current_key is not None and line:
                # 属于上一个块的续行（多行 Thought / 行尾附注）
                current_lines.append(line)
            # 标记出现之前的普通文字视为开场白，忽略

        if current_key is not None:
            blocks.append((current_key, current_lines))

        # 每个标签取最后出现的一块
        thought: Optional[str] = None
        action: Optional[str] = None
        for key, body_lines in blocks:
            joined = "\n".join(body_lines).strip()
            if not joined:
                continue
            if key == "thought":
                thought = joined
            else:
                action = joined
        return thought, action

    def _parse_action(self, action_text: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
        """解析 Action 正文，提取 ``(工具名, 入参)``。

        在整段正文中搜索第一个「标识符[...]」令牌，入参贪婪匹配到最后一个 ``]``，
        因此容忍入参内部出现方括号，也容忍动作之后跟有多余的文字。
        解析不到时返回 ``(None, None)``。
        """
        if not action_text:
            return None, None
        match = _ACTION_TOKEN.search(action_text)
        if match:
            tool_name = match.group(1).strip()
            tool_input = match.group(2).strip()
            return tool_name, tool_input
        return None, None

    def _parse_action_input(self, action_text: Optional[str]) -> str:
        """提取 Action 正文方括号内的内容（通常用于 Finish 的最终答案）。

        兼容父类同名方法的字符串返回值，方便外部代码按原接口调用。
        """
        _, tool_input = self._parse_action(action_text)
        return tool_input if tool_input is not None else ""
