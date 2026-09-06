"""三国狼人杀离线规则与消息流测试。"""

from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout

from game import ThreeKingdomsWerewolfGame, determine_winner, majority_target
from player_agents import DemoPlayer
from roles import STANDARD_ROSTER


class RuleTests(unittest.TestCase):
    def test_standard_roster_has_two_wolves_and_six_unique_players(self) -> None:
        self.assertEqual(len(STANDARD_ROSTER), 6)
        self.assertEqual(len({profile.name for profile in STANDARD_ROSTER}), 6)
        self.assertEqual(sum(profile.role == "狼人" for profile in STANDARD_ROSTER), 2)

    def test_winner_conditions(self) -> None:
        roles = {profile.name: profile.role for profile in STANDARD_ROSTER}
        self.assertEqual(determine_winner(["曹操", "张飞"], roles), "好人阵营")
        self.assertEqual(determine_winner(["孙权", "曹操"], roles), "狼人阵营")
        self.assertIsNone(determine_winner(["孙权", "曹操", "张飞"], roles))

    def test_tied_vote_eliminates_nobody(self) -> None:
        self.assertEqual(majority_target({"甲": "孙权", "乙": "周瑜"}), (None, 1))


class GameFlowTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.game = ThreeKingdomsWerewolfGame(DemoPlayer, max_rounds=1)

    async def test_wolves_never_target_a_wolf(self) -> None:
        with redirect_stdout(io.StringIO()):
            target = await self.game.werewolf_phase()
        self.assertEqual(target, "曹操")
        self.assertNotEqual(self.game.state.roles[target], "狼人")

    async def test_witch_antidote_is_consumed_once(self) -> None:
        with redirect_stdout(io.StringIO()):
            killed, poisoned = await self.game.witch_phase("曹操")
        self.assertIsNone(killed)
        self.assertIsNone(poisoned)
        self.assertFalse(self.game.state.antidote_available)

    async def test_agent_failure_falls_back_without_stopping_game(self) -> None:
        class FailingPlayer(DemoPlayer):
            async def act(self, request, schema):
                raise RuntimeError("模拟模型暂时不可用")

        game = ThreeKingdomsWerewolfGame(FailingPlayer, max_rounds=1)
        output = io.StringIO()
        with redirect_stdout(output):
            target = await game.werewolf_phase()
        self.assertEqual(target, "曹操")
        self.assertIn("已切换为本阶段安全决策", output.getvalue())

    async def test_one_round_demo_contains_all_major_phases(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            await self.game.run()
        text = output.getvalue()
        for marker in (
            "🎮 欢迎来到三国狼人杀！",
            "=== 游戏初始化 ===",
            "【狼人阶段】",
            "【预言家阶段】",
            "【女巫阶段】",
            "【白天讨论阶段】",
            "【投票阶段】",
        ):
            self.assertIn(marker, text)


if __name__ == "__main__":
    unittest.main()
