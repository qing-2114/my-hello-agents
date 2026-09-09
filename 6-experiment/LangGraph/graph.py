"""Compiled LangGraph workflow for the search assistant."""

from __future__ import annotations

from typing import Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

try:
    from .nodes import (
        generate_answer_node,
        tavily_search_node,
        understand_query_node,
    )
    from .state import SearchState
except ImportError:  # 支持直接运行 graph.py 的脚本模式。
    from nodes import generate_answer_node, tavily_search_node, understand_query_node
    from state import SearchState


def create_search_assistant(*, llm: Any | None = None, tavily_client: Any | None = None):
    """Build and compile the linear understand -> search -> answer workflow."""
    workflow = StateGraph(SearchState)
    workflow.add_node("understand", lambda state: understand_query_node(state, llm=llm))
    workflow.add_node("search", lambda state: tavily_search_node(state, tavily_client=tavily_client))
    workflow.add_node("answer", lambda state: generate_answer_node(state, llm=llm))
    workflow.add_edge(START, "understand")
    workflow.add_edge("understand", "search")
    workflow.add_edge("search", "answer")
    workflow.add_edge("answer", END)
    return workflow.compile(checkpointer=InMemorySaver())


def run_search(query: str, *, llm: Any | None = None, tavily_client: Any | None = None, thread_id: str = "default") -> SearchState:
    """Run one query through the compiled assistant."""
    app = create_search_assistant(llm=llm, tavily_client=tavily_client)
    initial_state: SearchState = {
        "messages": [("user", query)],
        "user_query": "",
        "search_query": "",
        "search_results": "",
        "final_answer": "",
        "step": "start",
    }
    return app.invoke(initial_state, config={"configurable": {"thread_id": thread_id}})


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="运行 LangGraph 搜索问答助手")
    parser.add_argument("query", nargs="?", help="可选：直接执行一个问题；省略时进入交互模式")
    args = parser.parse_args()

    if args.query:
        result = run_search(args.query)
        print(result["final_answer"])
    else:
        print("LangGraph 搜索问答助手已启动。输入 exit、quit 或 退出结束程序。")
        while True:
            try:
                query = input("\n请输入问题：").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n程序已退出。")
                break

            if query.lower() in {"exit", "quit", "退出"}:
                print("程序已退出。")
                break
            if not query:
                print("问题不能为空，请重新输入。")
                continue

            try:
                result = run_search(query)
                print(f"\n回答：\n{result['final_answer']}")
            except Exception as exc:
                print(f"\n本次请求失败：{exc}")
