"""Shared state for the LangGraph search assistant."""

from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages


class SearchState(TypedDict):
    """全局状态：在理解、搜索和回答节点之间传递。"""

    messages: Annotated[list, add_messages]
    user_query: str
    search_query: str
    search_results: str
    final_answer: str
    step: str
