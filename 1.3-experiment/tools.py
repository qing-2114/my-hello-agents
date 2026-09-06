"""Tools exposed to the travel agent.

The LLM should only choose a tool name and provide its arguments.  The
agent's main loop can then call ``available_tools[name](**arguments)``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

import requests
from dotenv import load_dotenv
from tavily import TavilyClient


# Load the single project-wide .env regardless of the current working directory.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")


# Deterministic local inventory for the ticketing experiment.  These are mock
# records, not live availability from an attraction or ticket platform.
_INITIAL_TICKET_INVENTORY = {
    "杭州": {
        "灵隐寺": {"remaining": 0, "price_yuan": 75},
        "雷峰塔": {"remaining": 0, "price_yuan": 40},
        "西溪国家湿地公园": {"remaining": 6, "price_yuan": 80},
        "杭州宋城": {"remaining": 3, "price_yuan": 320},
        "千岛湖中心湖区": {"remaining": 8, "price_yuan": 185},
    }
}
_ticket_inventory = {
    city: {name: record.copy() for name, record in attractions.items()}
    for city, attractions in _INITIAL_TICKET_INVENTORY.items()
}


def reset_mock_ticket_inventory() -> None:
    """Restore mock inventory so offline tests and demos are repeatable."""
    _ticket_inventory.clear()
    _ticket_inventory.update(
        {
            city: {name: record.copy() for name, record in attractions.items()}
            for city, attractions in _INITIAL_TICKET_INVENTORY.items()
        }
    )


def _ticket_result(**payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def check_ticket_availability(
    city: str,
    attraction: str,
    visit_date: str,
    quantity: int = 1,
) -> str:
    """Check deterministic mock availability for one attraction."""
    if quantity <= 0:
        return _ticket_result(status="INVALID_REQUEST", message="购票数量必须大于0。")
    record = _ticket_inventory.get(city.strip(), {}).get(attraction.strip())
    if record is None:
        return _ticket_result(
            status="NOT_FOUND",
            city=city,
            attraction=attraction,
            visit_date=visit_date,
            message="模拟票务库中没有该景点。",
        )
    remaining = int(record["remaining"])
    status = "AVAILABLE" if remaining >= quantity else "SOLD_OUT"
    return _ticket_result(
        status=status,
        city=city,
        attraction=attraction,
        visit_date=visit_date,
        requested=quantity,
        remaining=remaining,
        price_yuan=record["price_yuan"],
    )


def find_ticket_alternatives(
    city: str,
    visit_date: str,
    quantity: int = 1,
    exclude: list[str] | None = None,
) -> str:
    """Return available mock attractions without choosing one for the user."""
    excluded = {name.strip() for name in (exclude or [])}
    alternatives = []
    for name, record in _ticket_inventory.get(city.strip(), {}).items():
        if name in excluded or int(record["remaining"]) < quantity:
            continue
        alternatives.append(
            {
                "attraction": name,
                "remaining": record["remaining"],
                "price_yuan": record["price_yuan"],
            }
        )
    alternatives.sort(key=lambda item: (item["price_yuan"], item["attraction"]))
    return _ticket_result(
        status="ALTERNATIVES_FOUND" if alternatives else "NO_ALTERNATIVE",
        city=city,
        visit_date=visit_date,
        requested=quantity,
        alternatives=alternatives,
    )


def book_ticket(
    city: str,
    attraction: str,
    visit_date: str,
    quantity: int = 1,
    confirmed_by_user: bool = False,
) -> str:
    """Create a mock booking only after explicit user confirmation."""
    if not confirmed_by_user:
        return _ticket_result(
            status="CONFIRMATION_REQUIRED",
            attraction=attraction,
            message="用户尚未明确确认该景点、日期和数量。",
        )

    availability = json.loads(
        check_ticket_availability(city, attraction, visit_date, quantity)
    )
    if availability["status"] != "AVAILABLE":
        return _ticket_result(**availability)

    record = _ticket_inventory[city.strip()][attraction.strip()]
    record["remaining"] = int(record["remaining"]) - quantity
    return _ticket_result(
        status="BOOKED",
        order_id="MOCK-" + uuid4().hex[:10].upper(),
        city=city,
        attraction=attraction,
        visit_date=visit_date,
        quantity=quantity,
        total_price_yuan=int(record["price_yuan"]) * quantity,
        remaining=record["remaining"],
        message="模拟购票成功，未产生真实交易。",
    )


def get_weather(city: str) -> str:
    """Query the current weather for ``city`` through wttr.in."""
    city = city.strip()
    if not city:
        return "错误:城市名称不能为空。"

    url = f"https://wttr.in/{quote(city)}?format=j1"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        current_condition = data["current_condition"][0]
        weather_desc = current_condition["weatherDesc"][0]["value"]
        temp_c = current_condition["temp_C"]
        return f"{city}当前天气:{weather_desc}，气温{temp_c}摄氏度"
    except requests.exceptions.RequestException as exc:
        return f"错误:查询天气时遇到网络问题 - {exc}"
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        return f"错误:解析天气数据失败，可能是城市名称无效 - {exc}"


def get_attraction(city: str, weather: str) -> str:
    """Search Tavily and recommend attractions suitable for the weather."""
    city = city.strip()
    weather = weather.strip()
    if not city or not weather:
        return "错误:城市和天气不能为空。"

    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        return "错误:未配置TAVILY_API_KEY环境变量。"

    query = f"'{city}' 在'{weather}'天气下最值得去的旅游景点推荐及理由"
    try:
        tavily = TavilyClient(api_key=api_key)
        response = tavily.search(
            query=query,
            search_depth="basic",
            include_answer=True,
        )

        answer = response.get("answer")
        if answer:
            return str(answer)

        formatted_results = [
            f"- {result.get('title', '未命名结果')}: {result.get('content', '')}"
            for result in response.get("results", [])
        ]
        if not formatted_results:
            return "抱歉，没有找到相关的旅游景点推荐。"
        return "根据搜索，为您找到以下信息:\n" + "\n".join(formatted_results)
    except Exception as exc:  # Tavily SDK errors vary by version.
        return f"错误:执行Tavily搜索时出现问题 - {exc}"


# The main loop uses this registry to dispatch an LLM-selected action.
available_tools = {
    "get_weather": get_weather,
    "get_attraction": get_attraction,
    "check_ticket_availability": check_ticket_availability,
    "find_ticket_alternatives": find_ticket_alternatives,
    "book_ticket": book_ticket,
}


__all__ = [
    "available_tools",
    "book_ticket",
    "check_ticket_availability",
    "find_ticket_alternatives",
    "get_attraction",
    "get_weather",
    "reset_mock_ticket_inventory",
]
