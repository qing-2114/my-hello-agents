"""消息系统。"""

from datetime import datetime
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field


# 定义消息角色的类型，限制其取值。
MessageRole = Literal["user", "assistant", "system", "tool"]


class Message(BaseModel):
    """消息类。"""

    content: str
    role: MessageRole
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

    def __init__(self, content: str, role: MessageRole, **kwargs: Any):
        super().__init__(content=content, role=role, **kwargs)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式（OpenAI API 格式）。"""
        return {"role": self.role, "content": self.content}

    def __str__(self) -> str:
        return f"[{self.role}] {self.content}"
