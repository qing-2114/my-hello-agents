"""Nodes and client factories for the LangGraph search assistant."""

from __future__ import annotations

from datetime import date
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, SystemMessage
from tavily import TavilyClient

try:
    from .state import SearchState
except ImportError:  # 支持直接运行 graph.py 的脚本模式。
    from state import SearchState


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


def create_llm() -> Any:
    """Create the configured OpenAI-compatible chat model from the root .env."""
    try:
        from langchain_openai import ChatOpenAI
    except ImportError as exc:
        raise RuntimeError(
            "缺少 langchain-openai，请先安装 requirements.txt 中的依赖。"
        ) from exc

    api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "未配置 LLM_API_KEY（或 OPENAI_API_KEY），请在项目根目录 .env 中配置。"
        )

    kwargs: dict[str, Any] = {
        "api_key": api_key,
        "model": os.getenv("LLM_MODEL_ID") or os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        "temperature": 0,
    }
    base_url = os.getenv("LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL")
    if base_url:
        kwargs["base_url"] = base_url
    return ChatOpenAI(**kwargs)


def create_tavily_client() -> TavilyClient:
    """Create Tavily client using TAVILY_API_KEY from the root .env."""
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        raise RuntimeError("未配置 TAVILY_API_KEY，请在项目根目录 .env 中配置。")
    return TavilyClient(api_key=api_key)


def _response_text(response: Any) -> str:
    content = getattr(response, "content", response)
    if isinstance(content, list):
        return "".join(
            item.get("text", "") if isinstance(item, dict) else str(item)
            for item in content
        )
    return str(content)


def understand_query_node(state: SearchState, *, llm: Any | None = None) -> dict:
    """步骤1：理解用户查询并生成搜索关键词。"""
    messages = state.get("messages", [])
    if not messages:
        raise ValueError("SearchState.messages 不能为空。")
    user_message = str(getattr(messages[-1], "content", messages[-1])).strip()
    if not user_message:
        raise ValueError("用户查询不能为空。")

    today = date.today().isoformat()
    understand_prompt = f'''今天是 {today}。
分析用户的查询："{user_message}"
请完成两个任务：
1. 简洁总结用户想要了解什么
2. 生成最适合搜索引擎的关键词（中英文均可，要精准，优先使用“截至今天”“最新”“目前”等当前性表达）

要求：不要自行添加用户没有提到、且没有依据的具体年份；如果用户询问“现在”“目前”或“最新”，搜索词必须面向截至今天（{today}）的最新信息。

格式：
理解：[用户需求总结]
搜索词：[最佳搜索关键词]'''

    response_text = _response_text((llm or create_llm()).invoke([SystemMessage(content=understand_prompt)]))
    user_query = response_text.strip()
    summary_marker = "理解："
    if summary_marker in response_text:
        summary = response_text.split(summary_marker, 1)[1].strip().splitlines()[0].strip()
        if summary:
            user_query = summary

    search_query = user_message
    marker = "搜索词："
    if marker in response_text:
        candidate = response_text.split(marker, 1)[1].strip().splitlines()[0].strip()
        if candidate:
            search_query = candidate

    print(f"\n🧠 理解阶段: 我理解您的需求：{response_text}")

    return {
        "user_query": user_query,
        "search_query": search_query,
        "step": "understood",
        "messages": [AIMessage(content=f"我将为您搜索：{search_query}")],
    }


def _format_search_results(response: dict[str, Any]) -> str:
    chunks: list[str] = []
    answer = response.get("answer")
    if answer:
        chunks.append(f"Tavily answer:\n{answer}")
    for index, result in enumerate(response.get("results", []), start=1):
        title = result.get("title", "无标题")
        url = result.get("url", "")
        content = result.get("content", "").strip()
        chunks.append(f"[{index}] {title}\n链接：{url}\n摘要：{content}")
    return "\n\n".join(chunks) or "未找到相关搜索结果。"


def tavily_search_node(
    state: SearchState, *, tavily_client: Any | None = None
) -> dict:
    """步骤2：使用 Tavily API 搜索并格式化结果。"""
    search_query = state.get("search_query", "").strip()
    if not search_query:
        print("\n🔍 搜索阶段: ❌ 搜索关键词为空，无法搜索。")
        return {
            "search_results": "搜索失败：搜索关键词为空。",
            "step": "search_failed",
            "messages": [AIMessage(content="搜索遇到问题：搜索关键词为空。")],
        }
    try:
        print(f"\n🔍 正在搜索: {search_query}")
        response = (tavily_client or create_tavily_client()).search(
            query=search_query,
            search_depth="basic",
            max_results=5,
            include_answer=True,
        )
        search_results = _format_search_results(response)
        print("🔍 搜索阶段: ✅ 搜索完成！找到了相关信息，正在为您整理答案...")
        return {
            "search_results": search_results,
            "step": "searched",
            "messages": [AIMessage(content="搜索完成，正在整理答案...")],
        }
    except Exception as exc:
        print(f"\n🔍 搜索阶段: ❌ 搜索失败，将使用回退策略：{exc}")
        return {
            "search_results": f"搜索失败：{exc}",
            "step": "search_failed",
            "messages": [AIMessage(content="搜索遇到问题，将尝试基于已有知识回答...")],
        }


def generate_answer_node(state: SearchState, *, llm: Any | None = None) -> dict:
    """步骤3：基于搜索结果生成最终答案，搜索失败时回退到 LLM 知识。"""
    print("\n✍️ 回答阶段: 正在根据搜索结果生成最终答案...")
    if state.get("step") == "search_failed":
        prompt = (
            "搜索 API 暂时不可用，请基于您的知识回答用户的问题。\n"
            f"用户问题：{state.get('user_query', '')}"
        )
    else:
        prompt = (
            "基于以下搜索结果为用户提供完整、准确的答案。\n"
            f"用户问题：{state.get('user_query', '')}\n"
            f"搜索结果：\n{state.get('search_results', '')}\n"
            "请综合搜索结果，提供准确、有用的回答。涉及当前数量、日期、在售状态等"
            "时效性事实时，必须附上搜索结果中的来源链接；区分车系、车型和配置版本等"
            "不同统计口径。无法由搜索结果确认的内容请明确说明，不要自行补充。"
        )
    response_text = _response_text((llm or create_llm()).invoke([SystemMessage(content=prompt)]))
    print("✍️ 回答阶段: ✅ 答案生成完成！")
    return {
        "final_answer": response_text,
        "step": "completed",
        "messages": [AIMessage(content=response_text)],
    }
