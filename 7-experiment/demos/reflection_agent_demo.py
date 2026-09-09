"""第七章：使用通用 MyReflectionAgent 演示文本任务的反思迭代。

默认运行离线 FakeLLM，验证不局限于代码生成的“学习计划”任务；传入 ``--live``
后才会读取项目根目录的 .env 并调用真实 LLM。
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from dotenv import load_dotenv

from agents.my_reflection_agent import MyReflectionAgent


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"
REQUIRED_ENV_VARS = ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL_ID")


class DemoFakeLLM:
    """为离线 demo 提供确定性响应，不需要 API Key。"""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.provider = "offline-demo"
        self.model = "fake-reflection-model"

    def invoke(self, messages: list[dict[str, str]], **kwargs) -> str:
        prompt = messages[-1]["content"]
        self.calls.append(prompt)
        normalized_prompt = prompt.lstrip()
        if normalized_prompt.startswith("请根据以下要求完成任务"):
            return "建议每天学习数学、英语和专业课，并安排休息时间。"
        if normalized_prompt.startswith("请仔细审查以下回答"):
            return "回答缺少每天的具体安排，也没有说明如何根据课程和精力调整计划。"
        if normalized_prompt.startswith("请根据反馈意见改进你的回答"):
            return (
                "可以采用以下一周计划：周一至周五每天安排2小时专业课、1小时英语和"
                "1小时数学；周六复习错题并完成一个小项目；周日总结一周进度并预留"
                "半天休息。每天根据课程安排调整学习时段，连续学习50分钟后休息10分钟。"
            )
        raise AssertionError("demo 收到了未知提示词")


class LiveLLM:
    """Wrap the real LLM with progress output and bounded retries."""

    def __init__(self) -> None:
        from hello_agents import HelloAgentsLLM

        timeout = int(os.getenv("LLM_TIMEOUT", "30"))
        self._llm = HelloAgentsLLM(timeout=timeout)
        self._llm._client = self._llm._client.with_options(
            timeout=timeout,
            max_retries=0,
        )
        self.provider = self._llm.provider
        self.model = self._llm.model
        self.calls = 0

    def invoke(self, messages: list[dict[str, str]], **kwargs) -> str:
        self.calls += 1
        stages = ("INITIAL ANSWER", "REFLECTION", "REFINEMENT")
        stage = stages[min(self.calls - 1, len(stages) - 1)]
        separator = "-" * 20
        prompt = messages[-1]["content"]
        print(
            f"\n{separator}\n"
            f"[PROCESS {self.calls}/3] {stage}\n"
            f"provider={self.provider}, model={self.model}, "
            f"timeout={self._llm.timeout}s\n"
            f"{separator}\n"
            f"PROMPT:\n{prompt}\n"
            f"{separator}",
            flush=True,
        )
        kwargs.setdefault("max_tokens", 1200)
        kwargs.setdefault("extra_body", {"thinking": {"type": "disabled"}})
        response = self._llm.invoke(messages, **kwargs)
        print(
            f"\n{separator}\n"
            f"[PROCESS {self.calls}/3 RESULT] {stage}\n"
            f"{separator}\n"
            f"{response}\n"
            f"{separator}",
            flush=True,
        )
        return response


def load_project_environment() -> None:
    """加载并检查真实 LLM 所需配置。"""
    if not ENV_FILE.is_file():
        raise FileNotFoundError(f"未找到项目环境配置文件：{ENV_FILE}")
    load_dotenv(ENV_FILE)
    missing = [name for name in REQUIRED_ENV_VARS if not os.getenv(name)]
    if missing:
        raise RuntimeError(f"请在 {ENV_FILE} 中配置：{', '.join(missing)}")


def build_agent(live: bool) -> tuple[MyReflectionAgent, object]:
    """创建离线或真实 LLM 版本的 Agent。"""
    if live:
        load_project_environment()
        llm = LiveLLM()
    else:
        llm = DemoFakeLLM()
    return MyReflectionAgent("通用反思助手", llm, max_iterations=1), llm


def run_demo(live: bool = False) -> None:
    agent, llm = build_agent(live)
    task = "请为一名机器人专业大一学生设计一个可执行的一周学习计划。"
    answer = agent.run(task)

    print(f"模式：{'真实 LLM' if live else '离线 FakeLLM'}")
    print(f"任务：{task}")
    print(f"最终回答：\n{answer}")
    print(f"反思轨迹：\n{agent.get_trajectory()}")
    if isinstance(llm, DemoFakeLLM):
        print(f"离线验证通过：共调用 {len(llm.calls)} 次（初始回答、反思、改进）。")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="运行通用 Reflection Agent 示例")
    parser.add_argument(
        "--live",
        action="store_true",
        help="读取项目 .env 并调用真实 LLM；默认使用离线 FakeLLM",
    )
    return parser.parse_args()


if __name__ == "__main__":
    try:
        run_demo(live=parse_args().live)
    except KeyboardInterrupt:
        print("\nStopped by Ctrl+C.", flush=True)
    except Exception as exc:
        print(f"\nRun failed: {type(exc).__name__}: {exc}", flush=True)
        raise
