"""Multi-turn session support for the travel agent.

The existing ``max_steps`` setting limits one Thought/Action tool loop.  This
module adds a separate user-session lifecycle so feedback can arrive after a
completed recommendation without reusing that loop counter.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Literal
from uuid import uuid4

from agent import run_agent
from memory_store import DEFAULT_USER_ID, get_memory_context


FeedbackType = Literal["none", "accept", "reject"]
REFLECT_AFTER_REJECTIONS = 3
MAX_HISTORY_MESSAGES = 12


@dataclass
class Rejection:
    recommendation: str
    reason: str


@dataclass
class SessionState:
    """State that an API should persist by ``session_id``."""

    session_id: str
    user_id: str = DEFAULT_USER_ID
    messages: list[dict[str, str]] = field(default_factory=list)
    recent_rejections: list[Rejection] = field(default_factory=list)
    consecutive_rejections: int = 0
    reflection_count: int = 0
    strategy_context: str = ""
    last_recommendation: str | None = None


@dataclass
class TurnResult:
    answer: str
    reflected: bool
    consecutive_rejections: int
    strategy_version: int


def classify_feedback(
    user_input: str,
    last_recommendation: str | None,
    llm,
) -> FeedbackType:
    """Classify natural-language feedback against the previous recommendation."""
    if last_recommendation is None:
        return "none"

    prompt = (
        "上一条推荐：\n"
        + last_recommendation[-1500:]
        + "\n\n用户的新消息：\n"
        + user_input
        + "\n\n判断用户是否在接受或拒绝上一条推荐。"
        "如果用户只是提出新问题、补充信息或含义不明确，选择 NONE。"
    )
    system_prompt = (
        "你是反馈分类器。只允许输出一个标签："
        "REJECT、ACCEPT 或 NONE，不要解释。"
    )
    output = llm.generate(prompt, system_prompt=system_prompt).strip().upper()
    for label in ("REJECT", "ACCEPT", "NONE"):
        if output == label:
            return label.lower()  # type: ignore[return-value]
    return "none"


def _render_rejections(rejections: list[Rejection]) -> str:
    return "\n".join(
        f"{index}. 被拒绝的推荐：{item.recommendation}\n   用户原因：{item.reason}"
        for index, item in enumerate(rejections, 1)
    )


def _build_memory_query(state: SessionState, user_input: str) -> str:
    return "\n".join(
        [
            message["content"]
            for message in state.messages[-MAX_HISTORY_MESSAGES:]
            if message.get("role") == "user"
        ]
        + [user_input]
    )


def _reflect(state: SessionState, llm, memory_context: str) -> str:
    """Create a concise, reusable strategy without requesting chain-of-thought."""
    prompt = (
        "根据以下三次明确拒绝，输出一段不超过200字的后续推荐策略。"
        "只写：应避开什么、应优先什么、还缺什么关键信息。不要输出思维过程。"
        "用户只拒绝具体推荐但没有说明原因时，不得推断用户拒绝了整个活动类别，应先询问缺失偏好。\n\n"
        "必须继续遵守的用户长期偏好：\n"
        + memory_context
        + "\n\n最近三次拒绝：\n"
        + _render_rejections(state.recent_rejections[-REFLECT_AFTER_REJECTIONS:])
    )
    system_prompt = (
        "你是旅行推荐策略调整器。只总结可执行约束，不生成具体景点推荐。"
        "长期偏好优先于从模糊拒绝中得到的推测，除非用户当前明确修改了该偏好。"
    )
    strategy = llm.generate(prompt, system_prompt=system_prompt).strip()
    if not strategy or strategy.startswith("错误:"):
        # The feedback itself remains usable if the dedicated reflection call
        # fails; this keeps the next recommendation from ignoring it.
        strategy = "继续推荐前，避开以下已拒绝方案并优先询问用户缺失约束：\n" + _render_rejections(
            state.recent_rejections[-REFLECT_AFTER_REJECTIONS:]
        )
    return strategy[:1500]


def continue_session(
    state: SessionState,
    user_input: str,
    *,
    feedback_type: FeedbackType = "none",
    llm=None,
    max_steps_per_turn: int = 5,
    trace_memory: bool = False,
    on_strategy_updated: Callable[[str], None] | None = None,
) -> TurnResult:
    """Process one new user turn in an existing session.

    The caller should send ``feedback_type='reject'`` only when the user is
    rejecting ``state.last_recommendation``.  A rejection reason belongs in
    ``user_input``.  Counting is deterministic; the model never decides
    whether a message is a rejection.
    """
    if feedback_type not in {"none", "accept", "reject"}:
        raise ValueError("feedback_type 必须是 none、accept 或 reject。")
    if feedback_type == "reject" and state.last_recommendation is None:
        raise ValueError("当前会话还没有可拒绝的推荐。")

    session_memory_query = _build_memory_query(state, user_input)
    _, memory_context = get_memory_context(session_memory_query, user_id=state.user_id)
    reflected = False
    if feedback_type == "reject":
        state.consecutive_rejections += 1
        state.recent_rejections.append(
            Rejection(recommendation=state.last_recommendation or "", reason=user_input)
        )
        if state.consecutive_rejections >= REFLECT_AFTER_REJECTIONS:
            if llm is None:
                # Let run_agent create the normal client once, while keeping
                # the reflection call explicit for dependency injection/tests.
                from llm_client import create_deepseek_client

                llm = create_deepseek_client()
            state.strategy_context = _reflect(state, llm, memory_context)
            state.reflection_count += 1
            state.consecutive_rejections = 0
            reflected = True
            if on_strategy_updated is not None:
                on_strategy_updated(state.strategy_context)
    elif feedback_type == "accept":
        state.consecutive_rejections = 0
        state.recent_rejections.clear()

    answer = run_agent(
        user_input,
        max_steps=max_steps_per_turn,
        llm=llm,
        user_id=state.user_id,
        trace_memory=trace_memory,
        conversation_history=state.messages[-MAX_HISTORY_MESSAGES:],
        strategy_context=state.strategy_context,
        memory_query=session_memory_query,
    )
    state.messages.extend(
        [
            {"role": "user", "content": user_input},
            {"role": "assistant", "content": answer},
        ]
    )
    state.last_recommendation = answer
    return TurnResult(
        answer=answer,
        reflected=reflected,
        consecutive_rejections=state.consecutive_rejections,
        strategy_version=state.reflection_count,
    )


__all__ = [
    "FeedbackType",
    "SessionState",
    "TurnResult",
    "classify_feedback",
    "continue_session",
]


def run_interactive_session() -> None:
    """Keep accepting user turns after each completed Agent loop."""
    from llm_client import create_deepseek_client

    state = SessionState(session_id=str(uuid4()))
    llm = create_deepseek_client()
    print("已创建旅行会话：" + state.session_id)
    print("直接输入可继续聊天并自动识别接受或拒绝；也可用 /reject 原因或 /accept 明确标记；退出请输入 /exit。")

    while True:
        try:
            raw_input = input("\n你：").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n会话已结束。")
            return

        if not raw_input:
            continue
        if raw_input == "/exit":
            print("会话已结束。")
            return

        feedback_type: FeedbackType = "none"
        user_input = raw_input
        if raw_input == "/accept":
            feedback_type = "accept"
            user_input = "我接受这个推荐。"
        elif raw_input.startswith("/reject"):
            feedback_type = "reject"
            user_input = raw_input[len("/reject") :].strip()
            if not user_input:
                print("请在 /reject 后写明拒绝原因，例如：/reject 人太多了。")
                continue
        else:
            feedback_type = classify_feedback(
                user_input,
                state.last_recommendation,
                llm,
            )

        try:
            def show_strategy_update(strategy: str) -> None:
                print("\n[已根据连续 3 次拒绝调整推荐策略]")
                print("[新策略] " + strategy)

            result = continue_session(
                state,
                user_input,
                feedback_type=feedback_type,
                llm=llm,
                max_steps_per_turn=5,
                on_strategy_updated=show_strategy_update,
            )
        except ValueError as exc:
            print("输入错误：" + str(exc))
            continue

        print("\n智能体：" + result.answer)
        if feedback_type == "reject" and not result.reflected:
            print(f"[已识别为拒绝；当前连续拒绝 {result.consecutive_rejections} 次]")
        elif feedback_type == "accept":
            print("[已识别为接受；连续拒绝计数已清零]")


if __name__ == "__main__":
    run_interactive_session()
