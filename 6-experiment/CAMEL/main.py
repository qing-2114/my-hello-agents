"""用 CAMEL RolePlaying 生成《拖延症心理学》短篇电子书。

项目来源：https://hello-agents.datawhale.cc/
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import time
from pathlib import Path

from camel.agents import ChatAgent
from camel.messages import BaseMessage
from camel.models import ModelFactory
from camel.societies import RolePlaying
from camel.types import ModelPlatformType
from dotenv import load_dotenv

from ebook import clean_solution, response_content, upsert_chapter, write_artifacts
from prompts import (
    COLLABORATION_TASK,
    DETAILED_TASK,
    PSYCHOLOGIST_SYSTEM_PROMPT,
    WRITER_SYSTEM_PROMPT,
)


PROJECT_DIR = Path(__file__).resolve().parents[2]
DONE_MARKER = "<CAMEL_TASK_DONE>"


def required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"缺少环境变量 {name}，请检查项目根目录 .env")
    return value


def create_model():
    """创建 CAMEL 的 OpenAI 兼容模型后端。"""
    load_dotenv(PROJECT_DIR / ".env")
    return ModelFactory.create(
        model_platform=ModelPlatformType.OPENAI_COMPATIBLE_MODEL,
        model_type=required_env("LLM_MODEL_ID"),
        url=required_env("LLM_BASE_URL"),
        api_key=required_env("LLM_API_KEY"),
        model_config_dict={
            "temperature": float(os.getenv("CAMEL_TEMPERATURE", "0.4")),
            "max_tokens": int(os.getenv("CAMEL_MAX_TOKENS", "2600")),
        },
    )


def create_society(model) -> RolePlaying:
    """构建作家发指令、心理学家给方案的双智能体社会。"""
    psychologist = ChatAgent(
        BaseMessage.make_system_message(
            role_name="心理学家", content=PSYCHOLOGIST_SYSTEM_PROMPT
        ),
        model=model,
        output_language="中文",
    )
    writer = ChatAgent(
        BaseMessage.make_system_message(role_name="作家", content=WRITER_SYSTEM_PROMPT),
        model=model,
        output_language="中文",
    )
    return RolePlaying(
        assistant_role_name="心理学家",
        user_role_name="作家",
        task_prompt=DETAILED_TASK,
        with_task_specify=False,
        with_task_planner=False,
        assistant_agent=psychologist,
        user_agent=writer,
        output_language="中文",
    )


def print_message(role: str, content: str) -> None:
    print(f"\n{role}:\n{content}", flush=True)


def normalize_writer_display(content: str) -> str:
    """保证作家消息按 Instruction / Input 协议展示。"""
    text = content.strip()
    if DONE_MARKER in text:
        return DONE_MARKER
    if not re.match(r"^Instruction\s*:", text, flags=re.I):
        text = f"Instruction: {text}"
    if not re.search(r"(?m)^Input\s*:", text, flags=re.I):
        text += "\nInput: None"
    return text


def normalize_psychologist_display(content: str) -> str:
    """保证心理学家消息按 Solution / Next request 协议展示。"""
    text = content.strip()
    if not re.match(r"^Solution\s*:", text, flags=re.I):
        text = f"Solution:\n{text}"
    if not re.search(r"(?im)^Next request\.?\s*$", text):
        text += "\n\nNext request."
    return text


def agent_step_with_retry(agent, input_msg: BaseMessage, retries: int, role: str):
    """仅重试当前角色，避免另一角色的对话状态意外前进。"""
    for attempt in range(1, retries + 1):
        response = agent.step(input_msg)
        if getattr(response, "msgs", None):
            return response
        if attempt < retries:
            print(f"\n[{role}返回空消息，正在重试 {attempt}/{retries - 1}]", flush=True)
            time.sleep(1)
    raise RuntimeError(f"{role}连续 {retries} 次返回空消息")


def run(round_limit: int = 10, retries: int = 3) -> int:
    """运行角色扮演循环；返回实际完成的正文轮数。"""
    # 终端只展示教学协作轨迹；空响应会由下方中文重试提示明确反馈。
    logging.getLogger().setLevel(logging.ERROR)
    print("协作任务:", flush=True)
    print(COLLABORATION_TASK, flush=True)
    print("\n具体任务描述:", flush=True)
    print(DETAILED_TASK.split("\n\n协作规则：", maxsplit=1)[0], flush=True)

    model = create_model()
    society = create_society(model)
    chapters: list[str] = []
    trace: list[tuple[str, str]] = []
    input_msg = society.init_chat(
        "现在开始逐章协作。请只回复第一章的 Instruction 和 Input。"
    )

    try:
        for _ in range(round_limit):
            user_response = agent_step_with_retry(
                society.user_agent, input_msg, retries, "作家"
            )
            writer_content = response_content(user_response)

            if writer_content:
                writer_display = normalize_writer_display(writer_content)
                print_message("作家", writer_display)
                trace.append(("作家", writer_display))

            if DONE_MARKER in writer_content:
                break

            assistant_response = agent_step_with_retry(
                society.assistant_agent, user_response.msg, retries, "心理学家"
            )
            psychologist_content = response_content(assistant_response)
            if psychologist_content:
                psychologist_display = normalize_psychologist_display(
                    psychologist_content
                )
                print_message("心理学家", psychologist_display)
                trace.append(("心理学家", psychologist_display))
                chapter = clean_solution(psychologist_display)
                if chapter:
                    upsert_chapter(chapters, chapter)
                    # 长篇生成逐轮落盘，提供方中断时也保留已完成内容。
                    write_artifacts(chapters, trace)

            if assistant_response.terminated or user_response.terminated:
                break
            if not getattr(assistant_response, "msgs", None):
                break
            input_msg = assistant_response.msg
    except Exception:
        if chapters or trace:
            write_artifacts(chapters, trace)
            print("\n协作中断，已将完成的章节和轨迹写入 output 目录。", flush=True)
        raise

    ebook_path, trace_path, char_count = write_artifacts(chapters, trace)
    print("\n" + "=" * 60, flush=True)
    print(f"已完成章节：{len(chapters)}", flush=True)
    print(f"正文汉字数：{char_count}（目标 8000–10000）", flush=True)
    print(f"电子书：{ebook_path}", flush=True)
    print(f"协作轨迹：{trace_path}", flush=True)
    if not 8000 <= char_count <= 10000:
        print("提示：模型生成长度有波动，本次正文未落在目标区间，请检查后按需续写。")
    return len(chapters)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="运行 CAMEL 双智能体电子书协作")
    parser.add_argument("--round-limit", type=int, default=10, help="最大协作轮数")
    parser.add_argument("--retries", type=int, default=3, help="空响应最大尝试次数")
    args = parser.parse_args()
    if args.round_limit < 1:
        parser.error("--round-limit 必须大于 0")
    if args.retries < 1:
        parser.error("--retries 必须大于 0")
    return args


if __name__ == "__main__":
    cli_args = parse_args()
    run(cli_args.round_limit, cli_args.retries)
