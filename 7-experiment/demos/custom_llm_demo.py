"""第七章实验：使用自定义 MyLLM 和项目统一配置发起对话。

用法：
    # 仅检查 MyLLM 初始化，不调用 API
    python -m demos.custom_llm_demo --check
    # 使用项目根目录 .env 的统一配置发起真实调用
    python -m demos.custom_llm_demo
"""

from __future__ import annotations

import argparse
from pathlib import Path

from dotenv import load_dotenv

from agents.my_llm import MyLLM  # 注意：导入我们自己的类，而非框架原生的 HelloAgentsLLM

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"


def create_llm() -> MyLLM:
    """加载根目录 .env，并让 MyLLM 自动识别其中配置的供应商。"""
    if not ENV_FILE.is_file():
        raise FileNotFoundError(f"未找到项目环境配置文件：{ENV_FILE}")
    load_dotenv(ENV_FILE)
    return MyLLM()


def run_demo(check_only: bool = False) -> None:
    llm = create_llm()

    if check_only:
        print(
            "配置检查通过："
            f"provider={llm.provider}, model={llm.model}, "
            f"base_url={llm.base_url}"
        )
        return

    messages = [{"role": "user", "content": "你好，请介绍一下你自己。"}]

    # think 等方法从父类继承，无需重写
    print(f"{llm.provider} Response:")
    response_stream = llm.think(messages)
    for chunk in response_stream:
        # hello-agents 的 think 内部已打印响应内容，这里只需消费流即可
        pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="使用项目 .env 运行自定义 MyLLM 示例")
    parser.add_argument(
        "--check",
        action="store_true",
        help="仅检查 .env 和 MyLLM 初始化，不调用 LLM API",
    )
    return parser.parse_args()


if __name__ == "__main__":
    run_demo(check_only=parse_args().check)
