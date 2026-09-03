from __future__ import annotations

import ast
import re
from pathlib import Path

from llm_client import create_deepseek_client
from memory_store import DEFAULT_USER_ID, get_memory_context
from tools import available_tools


PROJECT_ROOT = Path(__file__).resolve().parent
SYSTEM_PROMPT_PATH = PROJECT_ROOT / "prompts" / "travel_agent.md"


def load_system_prompt() -> str:
    """Load the prompt from the repository so it can be edited without code changes."""
    return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8").strip()


def build_messages(user_input: str, user_id: str = DEFAULT_USER_ID) -> list[dict[str, str]]:
    """Build the messages payload expected by chat-style LLM APIs."""
    _, memory_context = get_memory_context(user_input, user_id=user_id)
    return [
        {"role": "system", "content": load_system_prompt() + "\n\n" + memory_context},
        {"role": "user", "content": user_input},
    ]


def invoke_tool(tool_name: str, **arguments) -> str:
    """Dispatch one action selected by the LLM through ``available_tools``."""
    tool = available_tools.get(tool_name)
    if tool is None:
        return f"错误:未知工具{tool_name!r}。可用工具:{', '.join(available_tools)}"
    try:
        return tool(**arguments)
    except TypeError as exc:
        return f"错误:工具{tool_name!r}的参数无效 - {exc}"


def parse_action(action: str) -> tuple[str, dict[str, object]] | str:
    """Parse the prompt's safe function-call or Finish action syntax."""
    action = action.strip()
    finish = re.fullmatch(r"Finish\[(.*)\]", action, flags=re.DOTALL)
    if finish:
        return finish.group(1)

    try:
        expression = ast.parse(action, mode="eval").body
    except SyntaxError as exc:
        raise ValueError(f"无法解析 Action: {action}") from exc
    if not isinstance(expression, ast.Call) or not isinstance(expression.func, ast.Name):
        raise ValueError(f"Action 必须是工具调用或 Finish[...]: {action}")
    if expression.args:
        raise ValueError("工具调用只支持具名参数。")
    arguments: dict[str, object] = {}
    for keyword in expression.keywords:
        if keyword.arg is None:
            raise ValueError("工具调用不支持 **kwargs。")
        try:
            arguments[keyword.arg] = ast.literal_eval(keyword.value)
        except (ValueError, SyntaxError) as exc:
            raise ValueError("工具参数必须是字符串、数字等字面量。") from exc
    return expression.func.id, arguments


def _first_thought_action(text: str) -> str:
    """Keep only the first Thought/Action pair from a model response."""
    match = re.search(
        r"(Thought:.*?Action:.*?)(?=\n\s*(?:Thought:|Action:|Observation:)|\Z)",
        text,
        flags=re.DOTALL,
    )
    if not match:
        return text.strip()
    truncated = match.group(1).strip()
    if truncated != text.strip():
        print("已截断多余的 Thought-Action 对")
    return truncated


def run_agent(
    user_input: str,
    max_steps: int = 5,
    llm=None,
    user_id: str = DEFAULT_USER_ID,
    trace_memory: bool = True,
    conversation_history: list[dict[str, str]] | None = None,
    strategy_context: str = "",
    memory_query: str | None = None,
) -> str:
    """Run the Thought/Action loop and execute registered tools.

    ``llm`` is injectable for tests; in normal use the DeepSeek client from
    ``.env`` is created automatically.  ``trace_memory`` prints retrieval and prompt injection stages.
    """
    client = llm or create_deepseek_client()
    # Retrieve once per user turn.  Keeping this outside the loop prevents the
    # same memory block from being duplicated in prompt_history every step.
    retrieval_query = memory_query or user_input
    memories, memory_context = get_memory_context(retrieval_query, user_id=user_id)
    system_prompt = load_system_prompt() + "\n\n" + memory_context
    if strategy_context.strip():
        system_prompt += (
            "\n\n# 当前会话的策略调整\n"
            "以下策略来自用户在本会话中的明确反馈。请遵守它，但不要向用户展示内部推理过程。\n"
            + strategy_context.strip()
        )

    prompt_history: list[str] = []
    for message in conversation_history or []:
        role = message.get("role", "unknown")
        content = message.get("content", "")
        prompt_history.append(f"历史{role}: {content}")
    prompt_history.append(f"用户请求: {user_input}")

    print(f"用户输入: {user_input}\n" + "=" * 40)
    if trace_memory:
        print("--- Memory injection trace ---")
        print("[1] retrieval query: " + retrieval_query)
        print("[2] retrieval user: " + user_id)
    if memories:
        print("已读取记忆: " + ", ".join(memory["id"] for memory in memories))
    else:
        print("已读取记忆: 无相关记忆")
    if trace_memory:
        print("[3] memory_context:")
        print(memory_context)
        print("[4] merged system_prompt:")
        print(system_prompt)
        print("[5] first user content:")
        print(prompt_history[0])
        print("--- Memory injection complete ---\n")
    for step in range(max_steps):
        print(f"--- 循环 {step + 1} ---\n")
        full_prompt = "\n".join(prompt_history)
        if trace_memory and step > 0:
            print("Reusing the same memory_context; no new retrieval this round.")
        llm_output = client.generate(full_prompt, system_prompt=system_prompt)
        llm_output = _first_thought_action(llm_output)
        print(f"模型输出:\n{llm_output}\n")
        prompt_history.append(llm_output)

        action_match = re.search(r"^Action:\s*(.+)$", llm_output, flags=re.MULTILINE)
        if not action_match:
            observation = "错误:未能解析到 Action 字段。请严格使用 Thought 和 Action 格式。"
            observation_str = f"Observation: {observation}"
            print(f"{observation_str}\n" + "=" * 40)
            prompt_history.append(observation_str)
            continue

        try:
            parsed = parse_action(action_match.group(1).strip())
        except ValueError as exc:
            observation = f"错误:{exc}"
            observation_str = f"Observation: {observation}"
            print(f"{observation_str}\n" + "=" * 40)
            prompt_history.append(observation_str)
            continue

        if isinstance(parsed, str):
            print(f"任务完成，最终答案: {parsed}")
            return parsed

        tool_name, kwargs = parsed
        observation = invoke_tool(tool_name, **kwargs)
        observation_str = f"Observation: {observation}"
        print(f"{observation_str}\n" + "=" * 40)
        prompt_history.append(observation_str)

    return f"错误:超过最大循环次数({max_steps})，任务未完成。"


if __name__ == "__main__":
    try:
        question = input("请输入旅行问题（直接回车使用示例）: ").strip()
        print(run_agent(question or "我周末想去杭州旅游。"))
    except (KeyboardInterrupt, EOFError):
        print("\n已退出。")
