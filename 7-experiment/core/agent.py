"""Agent 抽象基类。"""

from abc import ABC, abstractmethod
from typing import Optional

from hello_agents import HelloAgentsLLM

from .config import Config
from .message import Message


class Agent(ABC):
    """所有自定义 Agent 的抽象基类。"""

    def __init__(
        self,
        name: str,
        llm: HelloAgentsLLM,
        system_prompt: Optional[str] = None,
        config: Optional[Config] = None,
    ) -> None:
        self.name = name
        self.llm = llm
        self.system_prompt = system_prompt
        self.config = config or Config()
        self._history: list[Message] = []

    @abstractmethod
    def run(self, input_text: str, **kwargs) -> str:
        """运行 Agent 并返回文本结果。"""
        raise NotImplementedError

    def add_message(self, message: Message) -> None:
        """添加消息到历史记录。"""
        self._history.append(message)

    def clear_history(self) -> None:
        """清空历史记录。"""
        self._history.clear()

    def get_history(self) -> list[Message]:
        """获取历史记录的副本。"""
        return self._history.copy()

    def __str__(self) -> str:
        return f"Agent(name={self.name}, provider={self.llm.provider})"
