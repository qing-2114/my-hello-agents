"""三个研究 Agent 之间传递的数据。"""
from dataclasses import dataclass, field


@dataclass
class TodoItem:
    id: int
    title: str
    intent: str
    query: str


@dataclass
class SummaryState:
    research_topic: str
    todo_items: list[TodoItem] = field(default_factory=list)
