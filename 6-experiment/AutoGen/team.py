"""用 AutoGen RoundRobinGroupChat 模拟一个软件开发团队。

项目来源：https://hello-agents.datawhale.cc/
"""

from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

from autogen_agentchat.agents import AssistantAgent, UserProxyAgent
from autogen_agentchat.base import TaskResult
from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
from autogen_agentchat.messages import TextMessage
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_core.models import ModelFamily, ModelInfo
from autogen_ext.models.openai import OpenAIChatCompletionClient
from dotenv import load_dotenv

from workspace_tools import (
    APP_DIR,
    list_project_files,
    read_project_file,
    run_project_tests,
    validate_web_app,
    write_project_file,
)


PROJECT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_TASK = """我们需要开发一个比特币价格显示应用，具体要求如下：
1. 使用原生 HTML、CSS 和 JavaScript，无需构建步骤。
2. 实时显示比特币兑美元价格，首屏立即请求，之后每 30 秒刷新。
3. 清楚展示加载、成功、错误和最后更新时间状态。
4. 支持响应式布局、移动端体验和基本可访问性。
5. 所有文件写入 generated_app 目录。

请团队协作完成这个任务，从需求分析到最终实现。"""


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"缺少环境变量 {name}，请检查项目根目录 .env")
    return value


def create_model_client() -> OpenAIChatCompletionClient:
    """从根目录 .env 创建 OpenAI 兼容模型客户端，不泄露密钥。"""
    load_dotenv(PROJECT_DIR / ".env")
    return OpenAIChatCompletionClient(
        model=_required_env("LLM_MODEL_ID"),
        api_key=_required_env("LLM_API_KEY"),
        base_url=_required_env("LLM_BASE_URL"),
        timeout=float(os.getenv("LLM_TIMEOUT", "60")),
        max_tokens=6000,
        reasoning_effort="minimal",
        model_info=ModelInfo(
            vision=False,
            function_calling=True,
            json_output=False,
            family=ModelFamily.UNKNOWN,
            structured_output=False,
        ),
        parallel_tool_calls=False,
    )


def create_team(
    model_client: OpenAIChatCompletionClient,
    *,
    max_messages: int = 13,
    check_live_price: bool = True,
    auto_approve: bool = False,
) -> RoundRobinGroupChat:
    """创建固定顺序的四角色软件团队。"""
    product_manager = AssistantAgent(
        "ProductManager",
        model_client=model_client,
        model_client_stream=False,
        description="把业务目标转化为清晰、可验收的开发计划。",
        system_message="""你是产品经理。直接输出不超过 400 字的执行计划，不展示思考过程。
明确三个交付文件、CoinGecko bitcoin/usd 接口、30 秒刷新、状态和验收标准。
若 UserProxy 已确认需求完成，则简短致谢并说明可继续提供支持，不要重复制定计划。
不要写代码、不要调用工具、不要声称任务已验收。你发言后由 Engineer 接手。""",
    )

    engineer = AssistantAgent(
        "Engineer",
        model_client=model_client,
        model_client_stream=False,
        description="根据计划实现 Web 应用并修复评审发现的问题。",
        system_message="""你是工程师。立即使用工具实现，不展示思考过程，不反复讨论需求冲突。
根据产品计划以及最近的评审/验收反馈实现或修复应用。
必须实际调用 write_project_file 写入 generated_app/index.html、styles.css、app.js，不能只贴代码。
可先调用 list_project_files/read_project_file 了解已有实现。应用使用原生 HTML/CSS/JavaScript，
通过 CoinGecko simple price HTTPS API 获取 bitcoin/usd，首屏请求并每 30 秒刷新；不得嵌入密钥。
保持实现精炼，优先满足验收标准，不添加不必要的兼容层。
若 UserProxy 已确认需求完成，只需简短回应可继续提供技术支持，不要再次修改文件。
完成工具调用后简要列出你实际修改的文件，并以“请代码审查员检查”结尾；不要输出 APPROVE 或 TERMINATE。""",
        tools=[write_project_file, read_project_file, list_project_files],
        reflect_on_tool_use=True,
        max_tool_iterations=8,
    )

    code_reviewer = AssistantAgent(
        "CodeReviewer",
        model_client=model_client,
        model_client_stream=False,
        description="检查实现的正确性、可读性、健壮性与安全性。",
        system_message="""你是代码审查员。直接调用工具检查，不展示思考过程。必须先调用 list_project_files、read_project_file 和
run_project_tests 查看实际交付，不要仅依据 Engineer 的文字说明。重点检查行情字段解析、错误处理、
定时刷新、可访问性、响应式布局和代码可读性。给出明确结论和按优先级排列的可执行反馈；
若 UserProxy 已确认需求完成，只需简短致谢并说明愿意继续支持。
正常审查完成时以“代码审查完成，请用户代理测试”结尾；不要输出 APPROVE 或 TERMINATE，也不要修改文件。""",
        tools=[list_project_files, read_project_file, run_project_tests],
        reflect_on_tool_use=True,
        max_tool_iterations=8,
    )

    def automated_user_input(_prompt: str) -> str:
        report = validate_web_app(check_live_price=check_live_price)
        print("\n[UserProxy 自动验收]\n" + report)
        if report.startswith("PASS"):
            return "APPROVE\n最终用户验收通过。\n" + report
        return "最终用户验收未通过，请 Engineer 根据以下结果修复：\n" + report

    if auto_approve:
        user_input = automated_user_input
        user_description = "代表最终用户自动执行验收；只有验证通过才会批准交付。"
    else:
        user_input = input
        user_description = "代表最终用户在终端输入验收反馈或 TERMINATE 结束会话。"

    user_proxy = UserProxyAgent(
        "UserProxy",
        description=user_description,
        input_func=user_input,
    )

    termination = (
        TextMentionTermination("TERMINATE", sources=["UserProxy"])
        | TextMentionTermination("APPROVE", sources=["UserProxy"])
        | MaxMessageTermination(max_messages=max_messages)
    )
    # 数组顺序就是固定轮询顺序。
    return RoundRobinGroupChat(
        [product_manager, engineer, code_reviewer, user_proxy],
        termination_condition=termination,
    )


async def _display_text_messages(team: RoundRobinGroupChat, task: str) -> TaskResult:
    """只展示角色消息，过滤模型思考片段和底层工具事件。"""
    result: TaskResult | None = None
    async for event in team.run_stream(task=task):
        if isinstance(event, TextMessage):
            print(f"---------- TextMessage ({event.source}) ----------", flush=True)
            print(event.content, flush=True)
        elif isinstance(event, TaskResult):
            result = event
    if result is None:
        raise RuntimeError("群组会话未返回 TaskResult")
    return result


async def run(
    task: str,
    max_messages: int,
    check_live_price: bool,
    auto_approve: bool,
) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    print("🔧 正在初始化模型客户端...", flush=True)
    model_client = create_model_client()
    print("👥 正在创建智能体团队...", flush=True)
    team = create_team(
        model_client,
        max_messages=max_messages,
        check_live_price=check_live_price,
        auto_approve=auto_approve,
    )
    print("🚀 启动 AutoGen 软件开发团队协作...", flush=True)
    print("=" * 60, flush=True)
    try:
        result = await _display_text_messages(team, task)
        report = validate_web_app(check_live_price=False)
        user_finished = any(
            message.source == "UserProxy"
            and any(word in str(message.content) for word in ("TERMINATE", "APPROVE"))
            for message in result.messages
        )
        success = user_finished and report.startswith("PASS")
        print("=" * 60, flush=True)
        print("✅ 团队协作完成！" if success else "⚠️ 团队协作已停止，但尚未完成验收。")
        print("\n📋 协作结果摘要：")
        print("- 参与智能体数量：4个")
        print(f"- 任务完成状态：{'成功' if success else '未完成'}")
        print(f"- 交付目录：{APP_DIR}")
    finally:
        await model_client.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="运行 AutoGen 轮询式软件开发团队")
    parser.add_argument("--task", default=DEFAULT_TASK, help="交给团队的软件开发任务")
    parser.add_argument("--max-messages", type=int, default=13, help="最多群聊消息数（包含初始任务）")
    parser.add_argument(
        "--no-live-check",
        action="store_true",
        help="UserProxy 验收时跳过真实行情 API 连通性检查",
    )
    parser.add_argument(
        "--auto-approve",
        action="store_true",
        help="使用自动验收 UserProxy；默认在终端等待人工输入",
    )
    args = parser.parse_args()
    if args.max_messages < 5:
        parser.error("--max-messages 不能小于 5，需覆盖初始任务与四个角色")
    return args


if __name__ == "__main__":
    cli_args = parse_args()
    asyncio.run(
        run(
            task=cli_args.task,
            max_messages=cli_args.max_messages,
            check_live_price=not cli_args.no_live_check,
            auto_approve=cli_args.auto_approve,
        )
    )
