"""三国狼人杀命令行入口（AgentScope 2.x）。"""

from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

from agentscope.credential import DeepSeekCredential, OpenAICredential
from agentscope.formatter import DeepSeekMultiAgentFormatter, OpenAIMultiAgentFormatter
from agentscope.model import DeepSeekChatModel, OpenAIChatModel
from dotenv import load_dotenv

from game import ThreeKingdomsWerewolfGame
from player_agents import DemoPlayer, LivePlayer


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="基于 AgentScope 2.x 的三国狼人杀")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="使用确定性离线玩家，不发送真实 API 请求",
    )
    parser.add_argument(
        "--max-rounds",
        type=int,
        default=3,
        help="最大游戏轮数，默认 3",
    )
    return parser


def build_model():
    """从项目根目录 .env 构造 AgentScope 2.x 模型。"""

    load_dotenv(PROJECT_ROOT / ".env")
    api_key = os.getenv("LLM_API_KEY")
    base_url = os.getenv("LLM_BASE_URL")
    model_id = os.getenv("LLM_MODEL_ID")
    if not api_key or not model_id:
        raise RuntimeError("根目录 .env 必须配置 LLM_API_KEY 和 LLM_MODEL_ID")

    if base_url and "deepseek.com" in base_url.lower():
        credential = DeepSeekCredential(api_key=api_key, base_url=base_url)
        return DeepSeekChatModel(
            credential=credential,
            model=model_id,
            parameters=DeepSeekChatModel.Parameters(
                temperature=0.7,
                max_tokens=320,
            ),
            stream=False,
            formatter=DeepSeekMultiAgentFormatter(),
        )

    credential = OpenAICredential(api_key=api_key, base_url=base_url)
    return OpenAIChatModel(
        credential=credential,
        model=model_id,
        parameters=OpenAIChatModel.Parameters(
            temperature=0.7,
            max_tokens=320,
        ),
        stream=False,
        formatter=OpenAIMultiAgentFormatter(),
    )


async def async_main() -> None:
    args = build_parser().parse_args()
    if args.max_rounds < 1:
        raise SystemExit("--max-rounds 必须大于或等于 1")

    if args.demo:
        print("ℹ️ 当前为离线演示模式，不会调用 LLM API。")
        factory = DemoPlayer
    else:
        print("ℹ️ 当前为真实模型模式，将读取根目录 .env 并调用 LLM API。")
        model = build_model()
        factory = lambda profile: LivePlayer(profile, model)

    game = ThreeKingdomsWerewolfGame(factory, max_rounds=args.max_rounds)
    await game.run()


if __name__ == "__main__":
    asyncio.run(async_main())

