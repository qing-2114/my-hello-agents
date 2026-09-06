"""三国狼人杀的消息驱动游戏控制器。"""

from __future__ import annotations

import asyncio
from collections import Counter
from dataclasses import dataclass, field
from typing import Callable, Iterable

from agentscope.message import AssistantMsg, Msg, UserMsg
from pydantic import BaseModel

from player_agents import DemoPlayer, Player
from roles import STANDARD_ROSTER, PlayerProfile, is_werewolf, role_ability
from schemas import DayVoteAction, DiscussionAction, KillVoteAction, SeerAction, WitchAction


@dataclass(slots=True)
class GameState:
    """所有必须由代码裁定的权威游戏状态。"""

    roles: dict[str, str]
    alive: list[str]
    round_num: int = 0
    antidote_available: bool = True
    poison_available: bool = True
    seer_knowledge: dict[str, bool] = field(default_factory=dict)


def determine_winner(alive: Iterable[str], roles: dict[str, str]) -> str | None:
    """返回“好人阵营”“狼人阵营”或 None。"""

    alive_names = list(alive)
    wolves = sum(roles[name] == "狼人" for name in alive_names)
    good = len(alive_names) - wolves
    if wolves == 0:
        return "好人阵营"
    if wolves >= good:
        return "狼人阵营"
    return None


def majority_target(votes: dict[str, str | None]) -> tuple[str | None, int]:
    """统计有效票；最高票并列时无人出局。"""

    counts = Counter(target for target in votes.values() if target)
    if not counts:
        return None, 0
    top_count = max(counts.values())
    leaders = sorted(name for name, count in counts.items() if count == top_count)
    if len(leaders) != 1:
        return None, top_count
    return leaders[0], top_count


class ThreeKingdomsWerewolfGame:
    """主持游戏，并以 AgentScope 消息连接各玩家。"""

    def __init__(
        self,
        player_factory: Callable[[PlayerProfile], Player],
        *,
        max_rounds: int = 3,
    ) -> None:
        self.players = {profile.name: player_factory(profile) for profile in STANDARD_ROSTER}
        self.state = GameState(
            roles={profile.name: profile.role for profile in STANDARD_ROSTER},
            alive=[profile.name for profile in STANDARD_ROSTER],
        )
        self._fallback_players = {
            profile.name: DemoPlayer(profile) for profile in STANDARD_ROSTER
        }
        self.max_rounds = max_rounds

    def _alive_players(self) -> list[Player]:
        return [self.players[name] for name in self.state.alive]

    def _alive_by_role(self, role: str) -> list[Player]:
        return [
            self.players[name]
            for name in self.state.alive
            if self.state.roles[name] == role
        ]

    @staticmethod
    def _names(players: Iterable[Player]) -> str:
        return "、".join(player.name for player in players)

    async def announce(self, text: str, recipients: Iterable[Player] = ()) -> Msg:
        """生成主持人消息，可选地投递给指定玩家。"""

        print(f"游戏主持人: 📢 {text}")
        msg = UserMsg(name="游戏主持人", content=text)
        targets = list(recipients)
        if targets:
            await asyncio.gather(*(player.observe(msg) for player in targets))
        return msg

    async def _broadcast_reply(self, speaker: Player, action: BaseModel, recipients: list[Player]) -> None:
        statement = str(getattr(action, "statement"))
        print(f"{speaker.name}: {statement}")
        msg = AssistantMsg(
            name=speaker.name,
            content=statement,
            structured_output=action.model_dump(),
        )
        await asyncio.gather(
            *(player.observe(msg) for player in recipients if player.name != speaker.name),
        )

    def _legal_target(
        self,
        requested: str | None,
        candidates: list[str],
        *,
        actor: str,
        action_name: str,
    ) -> str | None:
        if requested in candidates:
            return requested
        fallback = candidates[0] if candidates else None
        print(f"⚠️ {actor} 的{action_name}目标无效，规则层改用：{fallback or '跳过'}")
        return fallback

    async def _safe_act(
        self,
        player: Player,
        request: Msg,
        schema: type[BaseModel],
    ) -> BaseModel:
        try:
            return await player.act(request, schema)
        except Exception as exc:
            print(
                f"⚠️ {player.name} 在 {schema.__name__} 阶段失败：{exc}；"
                "已切换为本阶段安全决策。",
            )
            return await self._fallback_players[player.name].act(request, schema)

    async def setup_game(self) -> None:
        print("\n=== 游戏初始化 ===")
        for profile in STANDARD_ROSTER:
            private_text = (
                f"【{profile.name}】你在这场三国狼人杀中扮演{profile.role}，"
                f"你的角色是{profile.name}。{role_ability(profile.role)}"
            )
            await self.announce(private_text, [self.players[profile.name]])

        await self.announce(
            f"三国狼人杀游戏开始！参与者：{self._names(self._alive_players())}",
            self._alive_players(),
        )
        print(f"✅ 游戏设置完成，共{len(self.state.alive)}名玩家")

    async def werewolf_phase(self) -> str | None:
        wolves = self._alive_by_role("狼人")
        if not wolves:
            return None

        print("\n【狼人阶段】")
        await self.announce("🐺 狼人请睁眼，选择今晚要击杀的目标...", wolves)
        candidates = [name for name in self.state.alive if self.state.roles[name] != "狼人"]
        request = await self.announce(
            f"狼人们，请讨论今晚的击杀目标。合法目标：{'、'.join(candidates)}",
            wolves,
        )
        for wolf in wolves:
            action = await self._safe_act(wolf, request, DiscussionAction)
            await self._broadcast_reply(wolf, action, wolves)

        vote_request = await self.announce(
            f"请选择击杀目标，只能从以下玩家中选择：{'、'.join(candidates)}",
            wolves,
        )
        actions = await asyncio.gather(
            *(self._safe_act(wolf, vote_request, KillVoteAction) for wolf in wolves),
        )
        votes: dict[str, str | None] = {}
        for wolf, raw_action in zip(wolves, actions):
            action = KillVoteAction.model_validate(raw_action)
            print(f"{wolf.name}: {action.statement}")
            votes[wolf.name] = self._legal_target(
                action.target,
                candidates,
                actor=wolf.name,
                action_name="击杀",
            )
        target, _ = majority_target(votes)
        return target or (candidates[0] if candidates else None)

    async def seer_phase(self) -> None:
        seers = self._alive_by_role("预言家")
        if not seers:
            return
        print("\n【预言家阶段】")
        seer = seers[0]
        candidates = [name for name in self.state.alive if name != seer.name]
        request = await self.announce(
            f"🔮 预言家请睁眼，只能查验：{'、'.join(candidates)}",
            [seer],
        )
        action = SeerAction.model_validate(await self._safe_act(seer, request, SeerAction))
        target = self._legal_target(action.target, candidates, actor=seer.name, action_name="查验")
        if target is None:
            return
        print(f"{seer.name}: {action.statement}")
        is_wolf = self.state.roles[target] == "狼人"
        self.state.seer_knowledge[target] = is_wolf
        await self.announce(
            f"查验结果：{target}是{'狼人' if is_wolf else '好人'}",
            [seer],
        )

    async def witch_phase(self, killed: str | None) -> tuple[str | None, str | None]:
        witches = self._alive_by_role("女巫")
        if not witches:
            return killed, None
        print("\n【女巫阶段】")
        witch = witches[0]
        status = (
            f"今晚{killed}被狼人击杀。"
            if killed
            else "今晚没有狼人击杀目标。"
        )
        request = await self.announce(
            "🧙‍♀️ 女巫请睁眼..."
            f"{status} 解药{'可用' if self.state.antidote_available else '已用'}，"
            f"毒药{'可用' if self.state.poison_available else '已用'}。",
            [witch],
        )
        action = WitchAction.model_validate(await self._safe_act(witch, request, WitchAction))
        print(f"{witch.name}: {action.statement}")

        final_killed = killed
        poisoned = None
        if action.use_antidote and killed and self.state.antidote_available:
            self.state.antidote_available = False
            final_killed = None
            await self.announce(f"你使用解药救了{killed}", [witch])

        poison_candidates = [name for name in self.state.alive if name != witch.name]
        if action.use_poison and self.state.poison_available:
            poisoned = self._legal_target(
                action.target_name,
                poison_candidates,
                actor=witch.name,
                action_name="毒杀",
            )
            if poisoned:
                self.state.poison_available = False
                await self.announce(f"你使用毒药毒杀了{poisoned}", [witch])
        return final_killed, poisoned

    def _remove_dead(self, names: Iterable[str | None]) -> list[str]:
        dead: list[str] = []
        for name in names:
            if name and name in self.state.alive and name not in dead:
                self.state.alive.remove(name)
                dead.append(name)
        return dead

    async def day_phase(self, night_deaths: list[str]) -> str | None:
        print("\n【白天讨论阶段】")
        await self.announce(f"☀️ 第{self.state.round_num}天天亮了，请大家睁眼...", self._alive_players())
        if night_deaths:
            await self.announce(f"昨夜阵亡：{'、'.join(night_deaths)}", self._alive_players())
        else:
            await self.announce("昨夜平安无事，无人死亡。", self._alive_players())

        alive_players = self._alive_players()
        request = await self.announce(
            f"现在开始自由讨论。存活玩家：{self._names(alive_players)}",
            alive_players,
        )
        for player in alive_players:
            action = await self._safe_act(player, request, DiscussionAction)
            await self._broadcast_reply(player, action, alive_players)

        print("\n【投票阶段】")
        vote_request = await self.announce("请投票选择要淘汰的玩家", alive_players)
        actions = await asyncio.gather(
            *(self._safe_act(player, vote_request, DayVoteAction) for player in alive_players),
        )
        votes: dict[str, str | None] = {}
        for player, raw_action in zip(alive_players, actions):
            action = DayVoteAction.model_validate(raw_action)
            candidates = [name for name in self.state.alive if name != player.name]
            target = self._legal_target(action.target, candidates, actor=player.name, action_name="放逐")
            votes[player.name] = target
            print(f"{player.name}: {action.statement}")

        voted_out, count = majority_target(votes)
        if voted_out:
            await self.announce(f"{voted_out}以{count}票被放逐。", self._alive_players())
        else:
            await self.announce("最高票出现并列，本轮无人被放逐。", self._alive_players())
        return voted_out

    async def run(self) -> str | None:
        print("🎮 欢迎来到三国狼人杀！")
        await self.setup_game()

        for round_num in range(1, self.max_rounds + 1):
            self.state.round_num = round_num
            print(f"\n=== 第{round_num}轮游戏 ===")
            print(f"🌙 第{round_num}夜降临，天黑请闭眼...")

            killed = await self.werewolf_phase()
            await self.seer_phase()
            final_killed, poisoned = await self.witch_phase(killed)
            night_deaths = self._remove_dead([final_killed, poisoned])

            winner = determine_winner(self.state.alive, self.state.roles)
            if winner:
                await self.announce(f"游戏结束，{winner}获胜！")
                return winner

            voted_out = await self.day_phase(night_deaths)
            self._remove_dead([voted_out])

            winner = determine_winner(self.state.alive, self.state.roles)
            if winner:
                await self.announce(f"游戏结束，{winner}获胜！")
                return winner
            print(f"第{round_num}轮结束，存活玩家：{self._names(self._alive_players())}")

        await self.announce("达到最大轮数，群雄暂且罢兵，游戏以未分胜负结束。")
        return None
