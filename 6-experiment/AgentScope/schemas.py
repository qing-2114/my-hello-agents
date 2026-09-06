"""AgentScope 结构化输出模型。"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, model_validator


class DiscussionAction(BaseModel):
    """公开讨论或狼人密议时的发言。"""

    statement: str = Field(min_length=2, max_length=220, description="符合三国人物性格的中文发言")
    reach_agreement: bool = Field(default=False, description="是否认为当前讨论已经形成共识")
    confidence: int = Field(default=5, ge=1, le=10, description="对判断的信心，1 到 10")


class KillVoteAction(BaseModel):
    """狼人夜间击杀投票。"""

    statement: str = Field(min_length=2, max_length=160, description="简短说明选择")
    target: str = Field(min_length=1, description="要击杀的存活好人姓名")


class SeerAction(BaseModel):
    """预言家查验。"""

    statement: str = Field(min_length=2, max_length=160, description="简短说明查验理由")
    target: str = Field(min_length=1, description="要查验的其他存活玩家姓名")


class WitchAction(BaseModel):
    """女巫夜间行动。"""

    statement: str = Field(min_length=2, max_length=200, description="说明是否用药及理由")
    use_antidote: bool = Field(description="是否使用解药")
    use_poison: bool = Field(description="是否使用毒药")
    target_name: Optional[str] = Field(default=None, description="使用毒药时的目标姓名")

    @model_validator(mode="after")
    def poison_requires_target(self) -> "WitchAction":
        if self.use_poison and not self.target_name:
            raise ValueError("使用毒药时必须指定 target_name")
        return self


class DayVoteAction(BaseModel):
    """白天放逐投票。"""

    statement: str = Field(min_length=2, max_length=180, description="投票理由")
    target: str = Field(min_length=1, description="要放逐的其他存活玩家姓名")

