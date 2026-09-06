"""AgentScope 2.x 玩家适配器与离线演示玩家。"""

from __future__ import annotations

from typing import Any, Protocol, TypeVar

from agentscope.agent import Agent, ReActConfig
from agentscope.message import AssistantMsg, Msg
from agentscope.model import ChatModelBase
from pydantic import BaseModel

from prompts import build_system_prompt
from roles import PlayerProfile
from schemas import DayVoteAction, DiscussionAction, KillVoteAction, SeerAction, WitchAction


ActionT = TypeVar("ActionT", bound=BaseModel)


class Player(Protocol):
    """游戏控制层依赖的最小玩家接口。"""

    profile: PlayerProfile

    @property
    def name(self) -> str: ...

    async def observe(self, msg: Msg) -> None: ...

    async def act(self, request: Msg, schema: type[ActionT]) -> ActionT: ...


class LivePlayer:
    """用 AgentScope 2.x Agent 驱动的真实模型玩家。"""

    def __init__(self, profile: PlayerProfile, model: ChatModelBase) -> None:
        self.profile = profile
        self._agent = Agent(
            name=profile.name,
            system_prompt=build_system_prompt(profile),
            model=model,
            react_config=ReActConfig(max_iters=4, structured_output_grace_iters=2),
        )

    @property
    def name(self) -> str:
        return self.profile.name

    async def observe(self, msg: Msg) -> None:
        await self._agent.observe(msg)

    async def act(self, request: Msg, schema: type[ActionT]) -> ActionT:
        reply = await self._agent.reply(request, structured_schema=schema)
        if reply.structured_output is None:
            raise ValueError(f"{self.name} 未返回结构化输出")
        return schema.model_validate(reply.structured_output)


class DemoPlayer:
    """不调用模型的确定性玩家，用于演示消息流和离线测试。"""

    def __init__(self, profile: PlayerProfile) -> None:
        self.profile = profile
        self.inbox: list[Msg] = []
        self._discussion_count = 0

    @property
    def name(self) -> str:
        return self.profile.name

    async def observe(self, msg: Msg) -> None:
        self.inbox.append(msg)

    async def act(self, request: Msg, schema: type[ActionT]) -> ActionT:
        self.inbox.append(request)
        data = self._scripted_data(schema)
        action = schema.model_validate(data)
        self.inbox.append(
            AssistantMsg(
                name=self.name,
                content=action.statement,
                structured_output=action.model_dump(),
            ),
        )
        return action

    def _scripted_data(self, schema: type[BaseModel]) -> dict[str, Any]:
        if schema is KillVoteAction:
            return {
                "statement": "曹操善察人心，今夜当先除之。",
                "target": "曹操",
            }
        if schema is SeerAction:
            return {
                "statement": "孙权看似持重，实则多次引导众人，我要查验孙权。",
                "target": "孙权",
            }
        if schema is WitchAction:
            return {
                "statement": "曹操既遭夜袭，俺先以解药相救，且看天明谁露破绽。",
                "use_antidote": True,
                "use_poison": False,
                "target_name": None,
            }
        if schema is DayVoteAction:
            targets = {
                "孙权": "曹操",
                "周瑜": "曹操",
                "曹操": "孙权",
                "张飞": "孙权",
                "司马懿": "孙权",
                "赵云": "孙权",
            }
            target = targets[self.name]
            return {
                "statement": f"综合昨夜与今日言行，我投{target}一票。",
                "target": target,
            }
        if schema is DiscussionAction:
            self._discussion_count += 1
            statements = {
                "孙权": "诸位，曹操惯于洞察人心，若任其掌握话语，江东局势恐受牵制。",
                "周瑜": "主公所言虽有理，但越是急于定罪，越可能掩盖真正的破绽。且看曹操如何自辩。",
                "曹操": "昨夜我察孙权气数有异，其身份可疑。宁教我负疑心，不可让群狼蒙混过关。",
                "张飞": "俺只认一个理：曹操昨夜确遭毒手，孙权却处处领着众人疑他，十分可疑！",
                "司马懿": "曹操遇袭而孙权持续推动放逐曹操，两件事相合，孙权的嫌疑正在上升。",
                "赵云": "夜袭目标与今日发言皆是证据。依在下看，应先查孙权的逻辑是否自洽。",
            }
            return {
                "statement": statements[self.name],
                "reach_agreement": self.name == "周瑜" and self.profile.role == "狼人",
                "confidence": 7,
            }
        raise TypeError(f"离线玩家不支持输出模型：{schema.__name__}")

